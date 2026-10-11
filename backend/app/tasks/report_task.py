"""Complete previous calendar periods, scheduled at 08:00 Asia/Shanghai."""

from app.tasks.reports import generate_report, scheduled_report

__all__ = ["generate_report", "scheduled_report"]
