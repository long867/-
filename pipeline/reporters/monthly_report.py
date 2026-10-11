"""Previous calendar-month reports, scheduled on the first day at 08:00."""

from datetime import datetime

from pipeline.reporters.common import build_report


async def generate_monthly_report(now: datetime | None = None) -> dict:
    """Generate last month's briefing with original observation series."""
    return await build_report("monthly", now)
