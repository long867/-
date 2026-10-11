"""Consistent calendar dates for Chinese citations and source labels."""

from datetime import datetime
from zoneinfo import ZoneInfo


def display_date(value: datetime | None) -> str:
    """Render the Shanghai date without changing stored UTC timestamps."""
    return (
        str(value.astimezone(ZoneInfo("Asia/Shanghai")).date())
        if value
        else "日期未提供"
    )
