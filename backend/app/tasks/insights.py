"""Periodic market signals and recoverable durable notification dispatch."""

import asyncio
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select

from app.core.cache import invalidate_public_cache
from app.core.db import SessionFactory
from app.models import Notice, NoticeDispatch
from app.services.notification_service import (
    create_price_notices,
    dispatch_one,
    prepare_dispatches,
)
from app.tasks.celery_app import celery_app
from pipeline.analyzers.event_ranker import rank_events

logger = structlog.get_logger()


async def refresh() -> dict:
    """Rank current events and publish unique warnings every five minutes."""
    async with SessionFactory.begin() as db:
        events = await rank_events(db)
        notice_ids = await create_price_notices(db)
        for notice_id in notice_ids:
            await prepare_dispatches(db, notice_id)
    await invalidate_public_cache()
    logger.info("insights_refreshed", events=len(events), price_alerts=len(notice_ids))
    return {"events": len(events), "price_alerts": len(notice_ids)}


@celery_app.task(
    name="miningintel.refresh_insights",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def refresh_insights() -> dict:
    return asyncio.run(refresh())


async def dispatch_pending() -> dict:
    """Recover pending work; flag workers lost after claiming network IO."""
    async with SessionFactory.begin() as db:
        notices = (
            await db.scalars(
                select(Notice.id).where(
                    Notice.created_at >= datetime.now(UTC) - timedelta(days=7)
                )
            )
        ).all()
        for notice_id in notices:
            await prepare_dispatches(db, notice_id)
        stranded = (
            await db.scalars(
                select(NoticeDispatch).where(
                    NoticeDispatch.status == "sending",
                    NoticeDispatch.claimed_at
                    < datetime.now(UTC) - timedelta(minutes=20),
                )
            )
        ).all()
        for work in stranded:
            work.status, work.last_error = "needs_review", "WorkerLostAfterClaim"
        ids = (
            await db.scalars(
                select(NoticeDispatch.id)
                .where(NoticeDispatch.status == "pending")
                .order_by(NoticeDispatch.created_at)
                .limit(100)
            )
        ).all()
    for dispatch_id in ids:
        send_notice.delay(str(dispatch_id))
    logger.info("notifications_dispatched", queued=len(ids), needs_review=len(stranded))
    return {"queued": len(ids), "needs_review": len(stranded)}


@celery_app.task(name="miningintel.dispatch_notifications")
def dispatch_notifications() -> dict:
    return asyncio.run(dispatch_pending())


@celery_app.task(name="miningintel.send_notice")
def send_notice(dispatch_id: str) -> dict:
    from uuid import UUID

    return asyncio.run(dispatch_one(UUID(dispatch_id)))
