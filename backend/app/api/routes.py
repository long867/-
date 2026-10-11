"""Versioned API for intelligence, users, consultations and operations."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import AwareDatetime
from sqlalchemy import func, select, update

from app.api.deps import DB, AdminUser, CurrentUser
from app.core.security import create_token, hash_password, verify_password
from app.models import (
    Article,
    Event,
    PipelineRun,
    Policy,
    PriceRecord,
    Report,
    Source,
    Subscription,
    User,
)
from app.schemas.api import (
    ArticleDetail,
    ArticleOut,
    ArticlePage,
    Credentials,
    EventOut,
    PolicyOut,
    PriceInput,
    PriceOut,
    ReportOut,
    ReviewInput,
    RunOut,
    SourceInput,
    SourceOut,
    SubscriptionInput,
    SubscriptionOut,
    TokenOut,
    UserOut,
)
from app.services.insights import get_insights
from app.services.prices import store_price
from pipeline.fetchers.http import validate_public_url

router = APIRouter(prefix="/api/v1")


@router.post("/auth/register", response_model=TokenOut, status_code=201, tags=["auth"])
async def register(payload: Credentials, db: DB) -> TokenOut:
    """Register a regular user; administration is provisioned only by CLI."""
    if await db.scalar(select(User.id).where(User.email == payload.email)):
        raise HTTPException(409, "邮箱已注册")
    user = User(email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)
    await db.flush()
    return TokenOut(
        access_token=create_token(user.id), user=UserOut.model_validate(user)
    )


@router.post("/auth/login", response_model=TokenOut, tags=["auth"])
async def login(payload: Credentials, db: DB) -> TokenOut:
    """Authenticate an active user and issue a short-lived access token."""
    user = await db.scalar(select(User).where(User.email == payload.email))
    if (
        user is None
        or not user.active
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(401, "邮箱或密码不正确")
    return TokenOut(
        access_token=create_token(user.id), user=UserOut.model_validate(user)
    )


@router.get("/auth/me", response_model=UserOut, tags=["auth"])
async def me(user: CurrentUser) -> User:
    return user


def article_filters(
    q: str | None,
    mineral: str | None,
    region: str | None,
    tag: str | None,
    category: str | None,
    start: datetime | None,
    end: datetime | None,
) -> list:
    """Build safe parameterized filters for public article queries."""
    conditions = [Article.status == "published"]
    if q:
        escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        conditions.append(
            func.concat_ws(
                " ",
                Article.title,
                Article.title_zh,
                Article.summary,
                Article.summary_zh,
            ).ilike(f"%{escaped}%", escape="\\")
        )
    for value, column in (
        (mineral, Article.minerals),
        (region, Article.regions),
        (tag, Article.tags),
    ):
        if value:
            conditions.append(column.contains([value]))
    if category:
        conditions.append(Article.category == category)
    if start:
        conditions.append(Article.published_at >= start)
    if end:
        conditions.append(Article.published_at < end)
    return conditions


@router.get("/articles", response_model=ArticlePage, tags=["intelligence"])
async def articles(
    db: DB,
    q: Annotated[str | None, Query(max_length=200)] = None,
    mineral: str | None = None,
    region: str | None = None,
    tag: str | None = None,
    category: Literal["news", "price", "policy", "report", "company"] | None = None,
    start: AwareDatetime | None = None,
    end: AwareDatetime | None = None,
    page: Annotated[int, Query(ge=1, le=10000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ArticlePage:
    """Published article stream with composable facets and bounded pagination."""
    if start and end and start >= end:
        raise HTTPException(422, "start 必须早于 end")
    conditions = article_filters(q, mineral, region, tag, category, start, end)
    total = await db.scalar(
        select(func.count()).select_from(Article).where(*conditions)
    )
    rows = (
        await db.scalars(
            select(Article)
            .where(*conditions)
            .order_by(
                Article.published_at.desc().nullslast(),
                Article.fetched_at.desc(),
                Article.id,
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return ArticlePage(
        items=[ArticleOut.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/articles/{article_id}", response_model=ArticleDetail, tags=["intelligence"]
)
async def article_detail(article_id: UUID, db: DB) -> Article:
    """Return original and translated text only after publication."""
    item = await db.get(Article, article_id)
    if item is None or item.status != "published":
        raise HTTPException(404, "文章不存在")
    return item


@router.get("/sources", tags=["intelligence"])
async def source_directory(db: DB) -> list[dict]:
    """Expose provenance metadata while keeping operational configuration private."""
    rows = (await db.scalars(select(Source).order_by(Source.name))).all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "url": row.url,
            "category": row.category,
            "language": row.language,
            "authority_score": row.authority_score,
        }
        for row in rows
    ]


@router.get("/facets", tags=["intelligence"])
async def facets(db: DB) -> dict:
    result = {}
    for name in ("minerals", "regions", "tags"):
        values = (
            select(func.unnest(getattr(Article, name)).label("value"))
            .where(Article.status == "published")
            .subquery()
        )
        rows = (
            await db.execute(
                select(values.c.value, func.count().label("count"))
                .group_by(values.c.value)
                .order_by(func.count().desc())
                .limit(50)
            )
        ).all()
        result[name] = [{"name": row[0], "count": row[1]} for row in rows]
    return result


@router.get("/events", response_model=list[EventOut], tags=["intelligence"])
async def events(
    db: DB,
    mineral: str | None = None,
    region: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> list[EventOut]:
    """Build public event summaries only from matching published evidence."""
    counts = (
        select(Article.event_id, func.count().label("count"))
        .where(Article.status == "published")
        .group_by(Article.event_id)
        .subquery()
    )
    candidates = select(Article.id, Article.event_id).where(
        Article.status == "published"
    )
    if mineral:
        candidates = candidates.where(Article.minerals.contains([mineral]))
    if region:
        candidates = candidates.where(Article.regions.contains([region]))
    representatives = (
        candidates.distinct(Article.event_id)
        .order_by(
            Article.event_id,
            Article.published_at.desc().nullslast(),
            Article.fetched_at.desc(),
            Article.id,
        )
        .subquery()
    )
    stmt = (
        select(Event, counts.c.count, Article)
        .join(counts, counts.c.event_id == Event.id)
        .join(representatives, representatives.c.event_id == Event.id)
        .join(Article, Article.id == representatives.c.id)
    )
    rows = (
        await db.execute(stmt.order_by(Event.last_updated_at.desc()).limit(limit))
    ).all()
    return [
        EventOut.model_validate(row[0]).model_copy(
            update={
                "article_count": row[1],
                "title_zh": row[2].title_zh or row[2].title,
                "summary_zh": row[2].summary_zh or row[2].summary,
                "minerals": row[2].minerals,
                "regions": row[2].regions,
                "importance_score": min(
                    100,
                    row[2].quality_score * 0.5
                    + row[2].relevance_score * 0.3
                    + min(row[1] * 4, 20),
                ),
            }
        )
        for row in rows
    ]


@router.get(
    "/events/{event_id}/articles",
    response_model=list[ArticleOut],
    tags=["intelligence"],
)
async def event_articles(event_id: UUID, db: DB) -> list[Article]:
    return list(
        (
            await db.scalars(
                select(Article)
                .where(Article.event_id == event_id, Article.status == "published")
                .order_by(Article.published_at.desc())
                .limit(100)
            )
        ).all()
    )


@router.get("/prices", response_model=list[PriceOut], tags=["intelligence"])
async def prices(
    db: DB,
    mineral: str | None = None,
    limit: Annotated[int, Query(ge=1, le=3650)] = 365,
) -> list[PriceRecord]:
    stmt = select(PriceRecord)
    if mineral:
        stmt = stmt.where(PriceRecord.mineral == mineral)
    return list(
        (await db.scalars(stmt.order_by(PriceRecord.date.desc()).limit(limit))).all()
    )


@router.get("/policies", response_model=list[PolicyOut], tags=["intelligence"])
async def policies(
    db: DB, country: str | None = None, mineral: str | None = None
) -> list[Policy]:
    stmt = (
        select(Policy)
        .join(Article, Article.url == Policy.url)
        .where(Article.status == "published")
    )
    if country:
        stmt = stmt.where(Policy.country == country)
    if mineral:
        stmt = stmt.where(Policy.minerals.contains([mineral]))
    return list(
        (
            await db.scalars(
                stmt.order_by(Policy.effective_date.desc().nullslast()).limit(100)
            )
        ).all()
    )


@router.get("/insights", tags=["intelligence"])
async def insights(db: DB) -> dict:
    """Return cached transparent hotspot and price anomaly calculations."""
    import json

    from fastapi.encoders import jsonable_encoder
    from redis.asyncio import Redis

    from app.core.config import get_settings

    client = Redis.from_url(
        get_settings().REDIS_URL, socket_timeout=1, socket_connect_timeout=1
    )
    try:
        try:
            cached = await client.get("insights:v1")
            if cached:
                return json.loads(cached)
        except Exception:
            pass
        result = await get_insights(db)
        try:
            await client.set("insights:v1", json.dumps(jsonable_encoder(result)), ex=30)
        except Exception:
            pass
        return result
    finally:
        await client.aclose()


@router.get("/reports", response_model=list[ReportOut], tags=["intelligence"])
async def reports(db: DB, kind: Literal["daily", "weekly"] = "daily") -> list[Report]:
    return list(
        (
            await db.scalars(
                select(Report)
                .where(Report.kind == kind)
                .order_by(Report.period_end.desc())
                .limit(30)
            )
        ).all()
    )


@router.get(
    "/subscriptions/me", response_model=SubscriptionOut | None, tags=["subscriptions"]
)
async def subscription(db: DB, user: CurrentUser) -> Subscription | None:
    return await db.scalar(select(Subscription).where(Subscription.user_id == user.id))


@router.put("/subscriptions/me", response_model=SubscriptionOut, tags=["subscriptions"])
async def update_subscription(
    payload: SubscriptionInput, db: DB, user: CurrentUser
) -> Subscription:
    from sqlalchemy.dialects.postgresql import insert

    await db.execute(
        insert(Subscription)
        .values(user_id=user.id, **payload.model_dump())
        .on_conflict_do_update(
            index_elements=[Subscription.user_id], set_=payload.model_dump()
        )
    )
    return await db.scalar(select(Subscription).where(Subscription.user_id == user.id))


@router.get(
    "/subscriptions/feed", response_model=list[ArticleOut], tags=["subscriptions"]
)
async def subscribed_feed(db: DB, user: CurrentUser) -> list[Article]:
    item = await db.scalar(select(Subscription).where(Subscription.user_id == user.id))
    if item is None:
        return []
    stmt = select(Article).where(Article.status == "published")
    if item.subscribed_minerals:
        stmt = stmt.where(Article.minerals.overlap(item.subscribed_minerals))
    if item.subscribed_regions:
        stmt = stmt.where(Article.regions.overlap(item.subscribed_regions))
    return list(
        (await db.scalars(stmt.order_by(Article.fetched_at.desc()).limit(100))).all()
    )


@router.get("/admin/sources", response_model=list[SourceOut], tags=["admin"])
async def admin_sources(db: DB, user: AdminUser) -> list[Source]:
    return list((await db.scalars(select(Source).order_by(Source.name))).all())


async def checked_source(payload: SourceInput) -> dict:
    """Validate destinations at registration and again at actual fetch time."""
    values = payload.model_dump()
    values["url"] = str(payload.url)
    try:
        await validate_public_url(values["url"])
    except (OSError, ValueError) as exc:
        raise HTTPException(422, "信源必须使用可解析的公网 HTTP(S) 地址") from exc
    return values


@router.post(
    "/admin/sources", response_model=SourceOut, status_code=201, tags=["admin"]
)
async def create_source(payload: SourceInput, db: DB, user: AdminUser) -> Source:
    values = await checked_source(payload)
    if await db.scalar(select(Source.id).where(Source.url == values["url"])):
        raise HTTPException(409, "信源地址已存在，请编辑已有信源")
    item = Source(**values)
    db.add(item)
    await db.flush()
    return item


@router.put("/admin/sources/{source_id}", response_model=SourceOut, tags=["admin"])
async def edit_source(
    source_id: UUID, payload: SourceInput, db: DB, user: AdminUser
) -> Source:
    item = await db.get(Source, source_id)
    if item is None:
        raise HTTPException(404, "信源不存在")
    values = await checked_source(payload)
    if await db.scalar(
        select(Source.id).where(Source.url == values["url"], Source.id != source_id)
    ):
        raise HTTPException(409, "信源地址已存在，请使用唯一地址")
    previous_name = item.name
    if item.url != values["url"]:
        item.etag = item.last_modified = item.last_fetched_at = None
    for key, value in values.items():
        setattr(item, key, value)
    if previous_name != item.name:
        await db.execute(
            update(Article)
            .where(Article.source_id == source_id)
            .values(indexed_at=None)
        )
    await db.flush()
    return item


@router.post("/admin/sources/{source_id}/fetch", status_code=202, tags=["admin"])
async def trigger_fetch(source_id: UUID, db: DB, user: AdminUser) -> dict:
    from app.tasks.ingest import fetch_source

    if await db.get(Source, source_id) is None:
        raise HTTPException(404, "信源不存在")
    result = fetch_source.delay(str(source_id))
    return {"task_id": result.id, "status": "queued"}


@router.delete("/admin/sources/{source_id}", status_code=204, tags=["admin"])
async def delete_source(source_id: UUID, db: DB, user: AdminUser) -> Response:
    """Delete unused sources; preserve provenance for sources with articles."""
    item = await db.get(Source, source_id, with_for_update=True)
    if item is None:
        raise HTTPException(404, "信源不存在")
    if await db.scalar(
        select(Article.id).where(Article.source_id == source_id).limit(1)
    ):
        raise HTTPException(409, "信源已有关联文章，请使用停用以保留来源")
    await db.delete(item)
    return Response(status_code=204)


@router.get("/admin/articles", response_model=list[ArticleOut], tags=["admin"])
async def review_queue(
    db: DB,
    user: AdminUser,
    status: Literal["pending", "processed", "published"] = "processed",
) -> list[Article]:
    return list(
        (
            await db.scalars(
                select(Article)
                .where(Article.status == status)
                .order_by(Article.fetched_at.desc())
                .limit(100)
            )
        ).all()
    )


@router.patch("/admin/articles/{article_id}", response_model=ArticleOut, tags=["admin"])
async def review_article(
    article_id: UUID, payload: ReviewInput, db: DB, user: AdminUser
) -> Article:
    item = await db.get(Article, article_id, with_for_update=True)
    if item is None:
        raise HTTPException(404, "文章不存在")
    if item.status == "pending":
        raise HTTPException(409, "必须先完成加工才能审核")
    item.status = payload.status
    item.indexed_at = None
    if payload.tags is not None:
        item.tags = sorted(set(payload.tags))
    from app.rag.indexer import enqueue_sync

    await enqueue_sync(db, item)
    return item


@router.post("/admin/articles/{article_id}/retry", status_code=202, tags=["admin"])
async def retry_article(article_id: UUID, db: DB, user: AdminUser) -> dict:
    """Requeue unpublished articles after committing the pending state."""
    from app.tasks.ingest import process_article

    item = await db.get(Article, article_id, with_for_update=True)
    if item is None:
        raise HTTPException(404, "文章不存在")
    if item.status == "published":
        raise HTTPException(409, "请先撤回到待审核状态，再重新加工")
    item.status = "pending"
    item.processing_error = None
    await db.commit()
    job = process_article.delay(str(article_id))
    return {"task_id": job.id, "status": "queued"}


@router.get("/admin/runs", response_model=list[RunOut], tags=["admin"])
async def runs(db: DB, user: AdminUser) -> list[PipelineRun]:
    return list(
        (
            await db.scalars(
                select(PipelineRun).order_by(PipelineRun.created_at.desc()).limit(100)
            )
        ).all()
    )


@router.get("/admin/tasks/{task_id}", tags=["admin"])
async def task_status(task_id: str, user: AdminUser) -> dict:
    """Unknown IDs are distinct from real queued tasks; omit raw Celery results."""
    import asyncio

    from app.core.task_history import snapshot

    item = await asyncio.to_thread(snapshot, task_id)
    return item or {"task_id": task_id, "state": "UNKNOWN"}


@router.post("/admin/prices", status_code=201, tags=["admin"])
async def import_price(payload: PriceInput, db: DB, user: AdminUser) -> dict:
    await store_price(db, payload)
    return {"status": "stored"}
