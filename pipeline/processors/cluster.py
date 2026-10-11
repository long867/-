"""Seven-day clustering with semantic/title gates and source-aware importance."""

import math
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Article, Event, Source
from pipeline.processors.dedup import title_similarity
from pipeline.processors.extractor import freshness


def importance(article_count: int, authority: float, recentness: float) -> float:
    """Weight report volume 40%, mean source authority 35% and freshness 25%."""
    volume = min(1, math.log1p(article_count) / math.log(11))
    return round(100 * (volume * 0.4 + authority / 10 * 0.35 + recentness * 0.25), 2)


async def cluster_article(db: AsyncSession, article: Article) -> None:
    """Attach once and atomically refresh event statistics and member relationships."""
    await db.execute(text("SELECT pg_advisory_xact_lock(27182818)"))
    if article.event_id is not None:
        event = await db.get(Event, article.event_id, with_for_update=True)
        if event and event.article_count == 1:
            event.title_zh = article.title_zh or article.title
            event.summary_zh = article.summary_zh or article.summary
            event.embedding = article.embedding
            event.minerals = article.minerals
            event.regions = article.regions
            event.last_updated_at = datetime.now(UTC)
        return
    now = datetime.now(UTC)
    observed = article.published_at or article.fetched_at or now
    # Old imports get their own event and cannot pull new reporting into an old story.
    base = select(Event).where(Event.first_seen_at >= now - timedelta(days=7))
    if article.minerals:
        base = base.where(Event.minerals.overlap(article.minerals))
    if article.regions:
        base = base.where(Event.regions.overlap(article.regions))
    event = None
    if observed >= now - timedelta(days=7):
        if article.embedding is not None:
            distance = Event.embedding.cosine_distance(article.embedding)
            candidates = (
                await db.scalars(
                    base.where(
                        Event.embedding.is_not(None),
                        distance <= 1 - get_settings().EVENT_SIMILARITY_THRESHOLD,
                    )
                    .order_by(distance)
                    .limit(20)
                    .with_for_update()
                )
            ).all()
            event = next(
                (
                    row
                    for row in candidates
                    if title_similarity(row.title_zh, article.title_zh or article.title)
                    >= 0.45
                ),
                None,
            )
        else:
            candidates = (
                await db.scalars(
                    base.order_by(Event.last_updated_at.desc())
                    .limit(200)
                    .with_for_update()
                )
            ).all()
            event = next(
                (
                    row
                    for row in candidates
                    if title_similarity(row.title_zh, article.title_zh or article.title)
                    >= 0.85
                ),
                None,
            )
    if event is None:
        event = Event(
            title_zh=article.title_zh or article.title,
            summary_zh=article.summary_zh or article.summary,
            minerals=article.minerals,
            regions=article.regions,
            embedding=article.embedding,
            article_count=0,
            first_seen_at=observed,
        )
        db.add(event)
        await db.flush()
    article.event_id = event.id
    event.last_updated_at = now
    event.minerals = sorted(set(event.minerals) | set(article.minerals))
    event.regions = sorted(set(event.regions) | set(article.regions))
    event.first_seen_at = min(event.first_seen_at, observed)
    await db.flush()
    count, authority, latest = (
        await db.execute(
            select(
                func.count(Article.id),
                func.avg(Source.authority_score),
                func.max(func.coalesce(Article.published_at, Article.fetched_at)),
            )
            .join(Source, Source.id == Article.source_id)
            .where(Article.event_id == event.id)
        )
    ).one()
    event.article_count = count
    event.importance_score = importance(
        count, float(authority or 0), freshness(latest, now)
    )
