"""Periodic grounded digests and durable opt-in email dispatch."""

import asyncio
from uuid import UUID

from app.services.digest_service import generate_digest
from app.services.subscription_service import deliver_report
from app.tasks.celery_app import celery_app


async def build_brief(kind: str) -> dict:
    """Refresh the live current-period digest; completed reports handle notification."""
    return await generate_digest(kind)


@celery_app.task(
    name="miningintel.generate_brief",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def generate_brief(kind: str = "daily") -> dict:
    """Build the current period only when its evidence has changed."""
    return asyncio.run(build_brief(kind))


@celery_app.task(name="miningintel.send_digest")
def send_digest(subscription_id: str, report_id: str) -> dict:
    return asyncio.run(deliver_report(UUID(subscription_id), UUID(report_id)))
