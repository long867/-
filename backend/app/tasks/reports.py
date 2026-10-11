"""Scheduled complete-calendar reports and consent-aware notification preparation."""

import asyncio
from uuid import UUID

from app.core.db import SessionFactory
from app.models import Report
from app.services.notification_service import create_report_notice, prepare_dispatches
from app.tasks.celery_app import celery_app
from pipeline.reporters.common import build_report


async def scheduled_report(kind: str) -> dict:
    """Generate the complete preceding period and atomically prepare durable notices."""
    result = await build_report(kind)
    if result.get("status") == "stale":
        raise RuntimeError("Report evidence changed during generation; retry required")
    if result.get("report_id"):
        async with SessionFactory.begin() as db:
            report = await db.get(Report, UUID(result["report_id"]))
            notice_id = await create_report_notice(db, report)
            await prepare_dispatches(db, notice_id)
        from app.tasks.insights import dispatch_notifications

        dispatch_notifications.delay()
    return result


@celery_app.task(
    name="miningintel.generate_report",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def generate_report(kind: str = "daily") -> dict:
    """Run the Shanghai-calendar schedule on a Celery worker."""
    if kind not in {"daily", "weekly", "monthly"}:
        raise ValueError("Unsupported report kind")
    return asyncio.run(scheduled_report(kind))
