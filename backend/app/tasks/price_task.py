"""Daily public quotations, isolated from licensed feeds and ordinary news fetching."""

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.db import SessionFactory
from app.models import Source
from app.tasks.celery_app import celery_app
from app.tasks.ingest import fetch_source, queue_lock

PUBLIC_PRICE_ADAPTERS = {"ppi_lithium_spot", "ppi_spot_market", "sunsirs_mineral_daily"}


@celery_app.task(
    name="miningintel.refresh_daily_prices",
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_jitter=True,
    max_retries=3,
)
def refresh_daily_prices() -> dict:
    """Queue permitted daily providers; retain source cooldowns and single-run locks."""
    lock = queue_lock("miningintel:schedule:daily-prices")
    if not lock.acquire():
        return {"status": "locked"}
    try:

        async def sources() -> list[str]:
            async with SessionFactory() as db:
                rows = (
                    await db.scalars(
                        select(Source).where(
                            Source.active.is_(True), Source.category == "price"
                        )
                    )
                ).all()
                return [
                    str(row.id)
                    for row in rows
                    if row.config_json.get("adapter") in PUBLIC_PRICE_ADAPTERS
                    and (
                        row.next_retry_at is None
                        or row.next_retry_at <= datetime.now(UTC)
                    )
                ]

        ids = asyncio.run(sources())
        for source_id in ids:
            fetch_source.delay(source_id)
        return {"status": "queued", "queued": len(ids)}
    finally:
        lock.release()
