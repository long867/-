"""Yesterday's daily report, scheduled at 08:00 in the configured report timezone."""

from datetime import datetime

from pipeline.reporters.common import build_report


async def generate_daily_report(now: datetime | None = None) -> dict:
    """Generate yesterday's complete daily briefing idempotently."""
    return await build_report("daily", now)
