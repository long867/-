"""Two-hour event reconciliation without changing existing event identities."""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.db import SessionFactory
from app.models import Article
from app.tasks.celery_app import celery_app
from pipeline.analyzers.event_ranker import rank_events
from pipeline.processors.cluster import cluster_article


async def reconcile() -> dict:
    """Recover recent unassigned evidence then refresh all published event ranks."""
    async with SessionFactory.begin() as db:
        rows = (
            await db.scalars(
                select(Article)
                .where(
                    Article.status.in_(["processed", "published"]),
                    Article.fetched_at >= datetime.now(UTC) - timedelta(days=7),
                    Article.event_id.is_(None),
                )
                .order_by(Article.fetched_at)
                .limit(500)
                .with_for_update()
            )
        ).all()
        for article in rows:
            await cluster_article(db, article)
        events = await rank_events(db)
        return {"clustered": len(rows), "ranked": len(events)}


@celery_app.task(
    name="miningintel.cluster_events",
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_jitter=True,
    max_retries=3,
)
def cluster_events() -> dict:
    """Reconcile a bounded batch; larger backlogs continue on the next scan."""
    return asyncio.run(reconcile())
