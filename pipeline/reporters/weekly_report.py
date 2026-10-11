"""Previous Monday–Monday reports, scheduled on Monday at 08:00."""

from datetime import datetime

from pipeline.reporters.common import build_report


async def generate_weekly_report(now: datetime | None = None) -> dict:
    """Generate last week's complete briefing idempotently."""
    return await build_report("weekly", now)
