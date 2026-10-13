"""Administrator-only task history, schedules, health and atomic batch review."""

import asyncio
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Response
from redis.exceptions import RedisError
from sqlalchemy import select

from app.api.deps import DB, AdminUser
from app.core.task_history import history
from app.models import Article
from app.rag.indexer import enqueue_sync
from app.schemas.operations import (
    BatchResult,
    BatchReview,
    ScheduleOut,
    SystemMetrics,
    TaskPage,
)
from app.services.operations_service import system_metrics

router = APIRouter(prefix="/api/v1/admin", tags=["operations"])


@router.get("/tasks", response_model=TaskPage)
async def tasks(
    user: AdminUser,
    response: Response,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    state: Literal["QUEUED", "STARTED", "RETRY", "SUCCESS", "FAILURE", "REVOKED"]
    | None = None,
) -> dict:
    """Expose persisted history even after Celery results expire."""
    response.headers["Cache-Control"] = "private, no-store"
    try:
        return await asyncio.to_thread(history, page, page_size, state)
    except RedisError as exc:
        raise HTTPException(503, "任务历史服务暂时不可用") from exc


@router.get("/system", response_model=SystemMetrics)
async def system(db: DB, user: AdminUser, response: Response) -> SystemMetrics:
    """Return actual database counts and recent error/liveness indicators."""
    response.headers["Cache-Control"] = "private, no-store"
    try:
        return await system_metrics(db)
    except RedisError as exc:
        raise HTTPException(503, "监控存储暂时不可用") from exc


@router.get("/schedule", response_model=list[ScheduleOut])
async def schedule(user: AdminUser, response: Response) -> list[ScheduleOut]:
    """Document configured cadence separately from proven runtime liveness."""
    from app.tasks.celery_app import celery_app

    response.headers["Cache-Control"] = "private, no-store"
    return [
        ScheduleOut(
            name=name,
            task=value["task"],
            schedule=str(value["schedule"]),
            timezone=celery_app.conf.timezone,
        )
        for name, value in celery_app.conf.beat_schedule.items()
    ]


@router.post("/articles/batch", response_model=BatchResult)
async def batch(payload: BatchReview, db: DB, user: AdminUser) -> BatchResult:
    """Validate the entire batch before changing visibility or processing."""
    ids = set(payload.article_ids)
    rows = (
        await db.scalars(
            select(Article)
            .where(Article.id.in_(ids))
            .order_by(Article.id)
            .with_for_update()
        )
    ).all()
    if len(rows) != len(ids):
        raise HTTPException(404, "部分文章不存在，批量操作未执行")
    if payload.action in {"publish", "hide"} and any(
        row.status == "pending" for row in rows
    ):
        raise HTTPException(409, "批量发布前必须完成所有文章的加工")
    for row in rows:
        row.status = {
            "publish": "published",
            "hide": "processed",
            "reprocess": "pending",
        }[payload.action]
        row.indexed_at = None
        if payload.action == "reprocess":
            row.processing_error = None
        await enqueue_sync(db, row)
    await db.commit()
    tasks = []
    deferred = False
    if payload.action == "reprocess":
        from app.tasks.ingest import enqueue_article

        for article_id in ids:
            try:
                task = await asyncio.to_thread(enqueue_article, str(article_id))
                if task is not None:
                    tasks.append(task.id)
            except Exception:
                # Durable pending state is recovered by the 15-minute scanner.
                deferred = True
    return BatchResult(
        changed=len(rows), queued=len(tasks), task_ids=tasks, dispatch_deferred=deferred
    )
