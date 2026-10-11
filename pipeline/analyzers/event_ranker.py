"""Rank events using their currently published evidence and source authority."""

from datetime import UTC, datetime

from app.models import Article, Event, Source
from app.services.article_service import public_conditions
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


def importance_score(article_count: int, authority: float, age_days: float) -> float:
    """Apply 0.4 count + 0.3 authority (1–10) + 0.3 freshness (0–10), capped at 100."""
    freshness = max(0.0, 10 * (1 - max(0, age_days) / 7))
    return round(min(100, article_count * 0.4 + authority * 0.3 + freshness * 0.3), 3)


async def rank_events(
    db: AsyncSession,
    now: datetime | None = None,
    *,
    persist: bool = True,
    since: datetime | None = None,
) -> list[dict]:
    """Recompute from published articles; hidden evidence cannot increase importance."""
    now = now or datetime.now(UTC)
    conditions = public_conditions() + [Article.published_at < now]
    if since:
        conditions.append(Article.published_at >= since)
    rows = (
        await db.execute(
            select(
                Event,
                func.count(Article.id),
                func.avg(Source.authority_score),
                func.max(Article.published_at),
            )
            .join(Article, Article.event_id == Event.id)
            .join(Source, Article.source_id == Source.id)
            .where(*conditions)
            .group_by(Event.id)
        )
    ).all()
    representatives = (
        await db.execute(
            select(
                Article.event_id,
                Article.title_zh,
                Article.title,
                Article.minerals,
                Article.regions,
            )
            .where(*conditions, Article.event_id.in_([event.id for event, *_ in rows]))
            .distinct(Article.event_id)
            .order_by(Article.event_id, Article.published_at.desc(), Article.id)
        )
    ).all()
    visible = {row[0]: row[1:] for row in representatives}
    results = []
    for event, count, authority, latest in rows:
        title_zh, title, minerals, regions = visible[event.id]
        score = importance_score(
            count, float(authority or 0), (now - latest).total_seconds() / 86400
        )
        if persist:
            event.importance_score = score
            event.article_count = count
        results.append(
            {
                "id": str(event.id),
                "title": title_zh or title,
                "article_count": count,
                "importance_score": score,
                "minerals": minerals,
                "regions": regions,
                "last_updated_at": latest.isoformat(),
            }
        )
    return sorted(results, key=lambda x: (-x["importance_score"], x["id"]))
