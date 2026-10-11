"""Six-hour full trend analysis, separate from timely five-minute price warnings."""

import asyncio
from datetime import UTC, datetime

from app.core.db import SessionFactory
from app.core.task_history import store_trends
from app.services.trend_service import hot_minerals, policy_updates, price_alerts
from app.tasks.celery_app import celery_app


async def analyze() -> dict:
    """Compute all observation windows from durable real records."""
    async with SessionFactory() as db:
        windows = {
            window: [
                item.model_dump(mode="json") for item in await hot_minerals(db, window)
            ]
            for window in ("24h", "48h", "7d")
        }
        policies = await policy_updates(db)
        prices = await price_alerts(db)
    result = {
        "updated_at": datetime.now(UTC).isoformat(),
        "windows": windows,
        "policy_count": len(policies),
        "price_alert_count": len(prices),
    }
    await asyncio.to_thread(store_trends, result)
    return {"windows": 3, "policies": len(policies), "price_alerts": len(prices)}


@celery_app.task(
    name="miningintel.analyze_trends",
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_jitter=True,
    max_retries=3,
)
def analyze_trends() -> dict:
    """Persist the latest completed trend snapshot for operators."""
    return asyncio.run(analyze())
