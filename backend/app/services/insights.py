"""Transparent trend counts rather than fabricated market predictions."""

from collections import Counter
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Article, PriceRecord


async def get_insights(db: AsyncSession) -> dict:
    """Compare last 24 hours with the preceding 24 hours using published records."""
    now = datetime.now(UTC)
    articles = (
        await db.scalars(
            select(Article).where(
                Article.status == "published",
                Article.fetched_at >= now - timedelta(hours=48),
            )
        )
    ).all()
    current = Counter(
        mineral
        for article in articles
        if article.fetched_at >= now - timedelta(hours=24)
        for mineral in article.minerals
    )
    previous = Counter(
        mineral
        for article in articles
        if article.fetched_at < now - timedelta(hours=24)
        for mineral in article.minerals
    )
    prices = (
        await db.scalars(
            select(PriceRecord)
            .where(
                PriceRecord.date >= (now - timedelta(days=7)).date(),
                (PriceRecord.change_pct >= get_settings().PRICE_ALERT_THRESHOLD)
                | (PriceRecord.change_pct <= -get_settings().PRICE_ALERT_THRESHOLD),
            )
            .order_by(PriceRecord.date.desc())
            .limit(20)
        )
    ).all()
    return {
        "window_hours": 24,
        "generated_at": now,
        "hotspots": [
            {
                "mineral": mineral,
                "count": count,
                "previous_count": previous[mineral],
                "growth_pct": round((count / previous[mineral] - 1) * 100, 2)
                if previous[mineral]
                else None,
                "is_new": previous[mineral] == 0,
            }
            for mineral, count in current.most_common(12)
        ],
        "price_alerts": [
            {
                "mineral": item.mineral,
                "price": str(item.price),
                "unit": item.unit,
                "currency": item.currency,
                "change_pct": str(item.change_pct),
                "date": item.date,
                "source": item.source,
            }
            for item in prices
        ],
    }
