"""Public event summaries derived exclusively from published supporting articles."""

from datetime import date
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article, Event, Source
from app.schemas.api import EventOut
from app.schemas.intelligence import EventDetail, EventPage
from app.services.article_service import article_out, date_bounds, public_conditions


async def list_events(
    db: AsyncSession,
    *,
    mineral: str | None = None,
    region: str | None = None,
    importance_score: float = 0,
    search: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 20,
    event_id: UUID | None = None,
) -> EventPage:
    """Filter public evidence before counting or ordering by event importance."""
    filters = public_conditions()
    lower, upper = date_bounds(date_from, date_to)
    if lower:
        filters.append(Article.published_at >= lower)
    if upper:
        filters.append(Article.published_at < upper)
    if mineral:
        filters.append(Article.minerals.contains([mineral]))
    if region:
        filters.append(Article.regions.contains([region]))
    if search:
        from app.services.article_service import escape_search

        filters.append(
            func.concat_ws(
                " ", Article.title, Article.title_zh, Article.summary_zh
            ).ilike("%" + escape_search(search) + "%", escape="\\")
        )
    if event_id:
        filters.append(Article.event_id == event_id)
    evidence = (
        select(
            Article.event_id.label("event_id"),
            func.count().label("count"),
            func.min(Article.published_at).label("first_seen"),
            func.max(Article.published_at).label("updated"),
            func.avg(Source.authority_score).label("authority"),
        )
        .join(Source, Article.source_id == Source.id)
        .where(*filters)
        .group_by(Article.event_id)
        .subquery()
    )
    age = func.greatest(
        0, func.extract("epoch", func.now() - evidence.c.updated) / 86400
    )
    freshness = func.greatest(0, 10 * (1 - age / 7))
    score = func.least(
        100, evidence.c.count * 0.4 + evidence.c.authority * 0.3 + freshness * 0.3
    )
    representatives = (
        select(Article.id, Article.event_id)
        .where(*filters)
        .distinct(Article.event_id)
        .order_by(Article.event_id, Article.published_at.desc().nullslast(), Article.id)
        .subquery()
    )
    stmt = (
        select(
            Event,
            evidence.c.count,
            evidence.c.first_seen,
            evidence.c.updated,
            score.label("score"),
            Article,
        )
        .join(evidence, evidence.c.event_id == Event.id)
        .join(representatives, representatives.c.event_id == Event.id)
        .join(Article, Article.id == representatives.c.id)
        .where(score >= importance_score)
    )
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (
        await db.execute(
            stmt.order_by(score.desc(), evidence.c.updated.desc().nullslast(), Event.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    items = []
    for event, count, first, updated, importance, representative in rows:
        items.append(
            EventOut.model_validate(event).model_copy(
                update={
                    "title_zh": representative.title_zh or representative.title,
                    "summary_zh": representative.summary_zh or representative.summary,
                    "article_count": count,
                    "first_seen_at": first or event.first_seen_at,
                    "last_updated_at": updated or event.last_updated_at,
                    "importance_score": float(importance),
                    "minerals": representative.minerals,
                    "regions": representative.regions,
                }
            )
        )
    return EventPage(items=items, total=total, page=page, page_size=page_size)


async def get_event(db: AsyncSession, event_id: UUID) -> EventDetail:
    """Return up to 100 reviewed reports attached to the visible event."""
    result = await list_events(db, event_id=event_id)
    if not result.items:
        raise HTTPException(404, "事件不存在")
    rows = (
        await db.execute(
            select(Article, Source.name)
            .join(Source)
            .where(*public_conditions(), Article.event_id == event_id)
            .order_by(Article.published_at.desc().nullslast(), Article.id)
            .limit(100)
        )
    ).all()
    return EventDetail(
        **result.items[0].model_dump(), articles=[article_out(*row) for row in rows]
    )
