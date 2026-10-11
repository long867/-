"""Comparable price observations, strict daily warnings and consecutive movements."""

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import PriceRecord
from app.schemas.intelligence import PriceAlert, PriceTrend


def analyze_prices(
    records: list[PriceRecord], today: date, threshold: float = 3
) -> tuple[list[PriceAlert], list[PriceTrend]]:
    """Never mix sources, products or units; never call multi-day changes daily.

    Consecutive moves mean successive quoted observations, with gaps <= four days.
    Observations outside seven calendar days supply a baseline only, never alerts.
    """
    groups: dict[tuple, list[PriceRecord]] = defaultdict(list)
    for row in records:
        if row.date <= today:
            groups[
                (
                    row.mineral,
                    row.product,
                    row.source,
                    row.unit,
                    row.currency,
                    row.price_type,
                )
            ].append(row)
    alerts: list[PriceAlert] = []
    trends: list[PriceTrend] = []
    since = today - timedelta(days=6)
    for rows in groups.values():
        rows.sort(key=lambda x: (x.date, str(x.id)))
        # Each source/product/day has one effective quote.
        rows = list({x.date: x for x in rows}.values())
        streak, direction = 0, "flat"
        for previous, current in zip(rows, rows[1:], strict=False):
            before, after = Decimal(str(previous.price)), Decimal(str(current.price))
            if before <= 0:
                streak, direction = 0, "flat"
                continue
            change = (after / before - 1) * 100
            gap = (current.date - previous.date).days
            move = "up" if change > 0 else "down" if change < 0 else "flat"
            if current.date < since or gap > 4 or move == "flat":
                streak, direction = 0, "flat"
            else:
                streak = streak + 1 if direction == move else 1
                direction = move
            if (
                current.date >= since
                and gap == 1
                and abs(change) > Decimal(str(threshold))
            ):
                magnitude = float(abs(change))
                alerts.append(
                    PriceAlert(
                        **{
                            **PriceAlert.model_validate(current).model_dump(),
                            "change_pct": float(round(change, 4)),
                            "previous_price": previous.price,
                            "previous_date": previous.date,
                            "severity": "red"
                            if magnitude >= 10
                            else "yellow"
                            if magnitude >= 5
                            else "green",
                            "direction": move,
                        },
                    )
                )
        latest = rows[-1]
        if latest.date >= since:
            trends.append(
                PriceTrend(
                    **{
                        **PriceTrend.model_validate(latest).model_dump(),
                        "direction": direction,
                        "consecutive_moves": streak,
                        "observations": [
                            {"date": x.date.isoformat(), "price": str(x.price)}
                            for x in rows
                            if x.date >= since
                        ],
                    },
                )
            )
    return sorted(
        alerts, key=lambda x: (x.date, abs(x.change_pct or 0)), reverse=True
    ), trends


async def price_analysis(
    db: AsyncSession, today: date | None = None
) -> tuple[list[PriceAlert], list[PriceTrend]]:
    """Load a bounded lookback, including preceding quotes for baseline comparisons."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    today = today or datetime.now(ZoneInfo(get_settings().DIGEST_TIMEZONE)).date()
    rows = (
        await db.scalars(
            select(PriceRecord).where(
                PriceRecord.date >= today - timedelta(days=14),
                PriceRecord.date <= today,
                ~PriceRecord.source.startswith("https://example.com/miningintel-demo/"),
            )
        )
    ).all()
    return analyze_prices(list(rows), today, get_settings().PRICE_ALERT_THRESHOLD)
