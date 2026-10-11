"""Single Celery Beat instance for automatic reports and market signals."""

import argparse
from pathlib import Path

from app.tasks.celery_app import celery_app


def main() -> None:
    """Start the durable scheduler; optionally exclude collection/NLP for a preview."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--insights-only", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    schedule = (
        root / "artifacts/celerybeat-insights"
        if args.insights_only
        else root / "artifacts/celerybeat-all"
    )
    if args.insights_only:
        names = {
            "daily-brief",
            "weekly-brief",
            "monthly-brief",
            "market-insights",
            "recover-notifications",
        }
        celery_app.conf.beat_schedule = {
            key: value
            for key, value in celery_app.conf.beat_schedule.items()
            if key in names
        }
    celery_app.start(["beat", "--loglevel=INFO", f"--schedule={schedule}"])


if __name__ == "__main__":
    main()
