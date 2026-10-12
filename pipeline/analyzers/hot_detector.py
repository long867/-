"""Coverage anomalies against non-overlapping historical windows, not forecasts."""

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from math import sqrt
from statistics import mean, pstdev
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article
from app.schemas.intelligence import HotMineral
from app.services.article_service import public_conditions

Window = Literal["24h", "48h", "7d"]
WINDOW_HOURS = {"24h": 24, "48h": 48, "7d": 168}


def detect_hotspots(
    observations: list[tuple[list[str], datetime]],
    window: Window = "7d",
    now: datetime | None = None,
) -> list[HotMineral]:
    """Require eight complete baseline windows and three nonzero historical bins.

    The Poisson floor avoids flagging trivial changes in sparse/constant series.
    Cold starts retain their real counts but cannot be declared statistical hotspots.
    """
    now = now or datetime.now(UTC)
    span = timedelta(hours=WINDOW_HOURS[window])
    baseline_size = 8 if window == "7d" else 14 if window == "48h" else 28
    start = now - span
    by_mineral: dict[str, list[datetime]] = defaultdict(list)
    earliest = min((stamp for _, stamp in observations), default=now)
    for minerals, stamp in observations:
        if stamp <= now:
            for mineral in set(minerals):
                by_mineral[mineral].append(stamp)
    result = []
    for mineral, stamps in by_mineral.items():
        current = sum(start <= stamp <= now for stamp in stamps)
        if not current:
            continue
        baseline = [
            sum(start - span * (i + 1) <= stamp < start - span * i for stamp in stamps)
            for i in range(baseline_size)
        ]
        complete = min(baseline_size, max(0, int((start - earliest) / span)))
        prior = baseline[0]
        avg = mean(baseline[:complete]) if complete else 0.0
        deviation = pstdev(baseline[:complete]) if complete else 0.0
        sufficient = complete >= 8 and sum(n > 0 for n in baseline[:complete]) >= 3
        sigma = max(deviation, sqrt(max(avg, 1.0)))
        z = (current - avg) / sigma if sufficient else None
        sparkline = [
            sum(
                now - timedelta(days=7 - i) <= stamp < now - timedelta(days=6 - i)
                for stamp in stamps
            )
            for i in range(7)
        ]
        result.append(
            HotMineral(
                mineral=mineral,
                count=current,
                previous_count=prior,
                growth_pct=round((current / prior - 1) * 100, 2) if prior else None,
                is_new=prior == 0,
                window=window,
                heat_score=round(min(100, max(0, (z or 0) * 20)), 2),
                is_hot=bool(sufficient and current >= 3 and z is not None and z > 2),
                trend="up"
                if current > prior
                else "down"
                if current < prior
                else "flat",
                baseline_mean=round(avg, 3),
                baseline_std=round(deviation, 3),
                baseline_samples=complete,
                baseline_sufficient=sufficient,
                z_score=round(z, 3) if z is not None else None,
                sparkline=sparkline,
            )
        )
    largest = max((row.count for row in result), default=1)
    for row in result:
        # Cross-sectional attention is distinct from a historical anomaly score.
        row.attention_score = round(row.count / largest * 100, 1)
    return sorted(result, key=lambda x: (-x.is_hot, -x.heat_score, -x.count, x.mineral))


async def hot_minerals(
    db: AsyncSession, window: Window = "7d", now: datetime | None = None
) -> list[HotMineral]:
    """Read only published evidence, bounded to nine weeks, with no article bodies."""
    now = now or datetime.now(UTC)
    rows = (
        await db.execute(
            select(Article.minerals, Article.published_at).where(
                *public_conditions(),
                Article.published_at >= now - timedelta(days=64),
                Article.published_at <= now,
            )
        )
    ).all()
    return detect_hotspots(
        [(list(names), stamp) for names, stamp in rows], window, now
    )[:20]
