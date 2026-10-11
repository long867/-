"""Generate complete daily, weekly or monthly reports, optionally backfilling dates."""

import argparse
import asyncio
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.core.logging import configure_logging

from pipeline.reporters.common import build_report


def main() -> None:
    """Run report builders without notifying external recipients by default."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--kind", choices=["daily", "weekly", "monthly"], default="daily"
    )
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        help="Generate the complete period preceding this local calendar date",
    )
    args = parser.parse_args()
    configure_logging(get_settings().LOG_LEVEL)
    now = (
        datetime.combine(args.as_of, time(8), ZoneInfo(get_settings().DIGEST_TIMEZONE))
        if args.as_of
        else None
    )

    async def run() -> dict:
        result = await build_report(args.kind, now)
        if result.get("report_id"):
            from uuid import UUID

            from app.core.db import SessionFactory
            from app.models import Report
            from app.services.notification_service import create_report_notice

            async with SessionFactory.begin() as db:
                report = await db.get(Report, UUID(result["report_id"]))
                await create_report_notice(db, report)
        return result

    print(asyncio.run(run()))


if __name__ == "__main__":
    main()
