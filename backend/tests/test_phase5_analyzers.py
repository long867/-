"""Statistical false-positive controls, calendar boundaries and comparable prices."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from app.models import PriceRecord

from pipeline.analyzers.event_ranker import importance_score
from pipeline.analyzers.hot_detector import detect_hotspots
from pipeline.analyzers.policy_tracker import policy_themes
from pipeline.analyzers.price_analyzer import analyze_prices
from pipeline.reporters.common import previous_period


def quote(
    day: date, value: str, *, source: str = "real-series", unit: str = "吨"
) -> PriceRecord:
    """Construct observations without inserting a fixture into the public corpus."""
    return PriceRecord(
        id=uuid4(),
        mineral="锂",
        product="碳酸锂",
        source=source,
        unit=unit,
        currency="CNY",
        price_type="spot",
        price=Decimal(value),
        date=day,
        change_pct=None,
        source_url=None,
    )


@pytest.mark.parametrize("window", ["24h", "48h", "7d"])
def test_coverage_cold_start_is_never_a_statistical_hotspot(window):
    now = datetime(2026, 10, 11, 8, tzinfo=UTC)
    hits = detect_hotspots(
        [(["锂"], now - timedelta(hours=i)) for i in range(5)], window, now
    )
    assert hits[0].count == 5
    assert not hits[0].is_hot and not hits[0].baseline_sufficient
    assert hits[0].z_score is None


def test_steady_coverage_is_not_flagged_but_a_real_burst_is():
    now = datetime(2026, 10, 11, 8, tzinfo=UTC)
    history = [(["锂"], now - timedelta(days=i, hours=1)) for i in range(65)]
    steady = detect_hotspots(history, "24h", now)[0]
    assert steady.baseline_sufficient and not steady.is_hot
    burst = detect_hotspots(
        history + [(["锂"], now - timedelta(minutes=i + 1)) for i in range(8)],
        "24h",
        now,
    )[0]
    assert burst.is_hot and burst.z_score > 2 and burst.heat_score > 0
    assert len(burst.sparkline) == 7


def test_hot_detector_deduplicates_mineral_tags_and_ignores_future_articles():
    now = datetime.now(UTC)
    hits = detect_hotspots(
        [(["铜", "铜"], now), (["铜"], now + timedelta(hours=1))], "24h", now
    )
    assert hits[0].count == 1


@pytest.mark.parametrize(
    "kind,now,start,end",
    [
        (
            "daily",
            datetime(2026, 10, 10, 18, tzinfo=UTC),
            date(2026, 10, 10),
            date(2026, 10, 11),
        ),
        (
            "weekly",
            datetime(2026, 10, 11, 1, tzinfo=UTC),
            date(2026, 9, 28),
            date(2026, 10, 5),
        ),
        (
            "monthly",
            datetime(2027, 1, 1, tzinfo=UTC),
            date(2026, 12, 1),
            date(2027, 1, 1),
        ),
        (
            "monthly",
            datetime(2024, 3, 1, tzinfo=UTC),
            date(2024, 2, 1),
            date(2024, 3, 1),
        ),
    ],
)
def test_complete_report_periods_respect_timezone_week_boundaries_and_leap_year(
    kind, now, start, end
):
    lower, upper = previous_period(kind, now)
    assert lower.date() == start and upper.date() == end
    assert str(lower.tzinfo) == "Asia/Shanghai"


def test_exact_three_percent_is_not_alerted_and_cross_source_changes_are_not_compared():
    day = date(2026, 10, 11)
    alerts, _ = analyze_prices(
        [
            quote(day - timedelta(days=1), "100"),
            quote(day, "103"),
            quote(day, "200", source="other"),
        ],
        day,
    )
    assert not alerts
    alerts, _ = analyze_prices(
        [quote(day - timedelta(days=1), "100"), quote(day, "104")], day
    )
    assert len(alerts) == 1 and alerts[0].change_pct == Decimal("4.0000")
    assert alerts[0].previous_price == Decimal("100") and alerts[0].severity == "green"


def test_missing_days_do_not_make_daily_alerts_but_quotes_remain_consecutive():
    day = date(2026, 10, 11)
    rows = [
        quote(day - timedelta(days=3), "100"),
        quote(day - timedelta(days=2), "105"),
        quote(day, "112"),
    ]
    alerts, trends = analyze_prices(rows, day)
    assert len(alerts) == 1
    assert alerts[0].date == day - timedelta(days=2)
    assert trends[0].direction == "up" and trends[0].consecutive_moves == 2
    assert len(trends[0].observations) == 3


def test_zero_baseline_stale_quotes_and_different_units_cannot_make_false_alerts():
    day = date(2026, 10, 11)
    alerts, _ = analyze_prices(
        [
            quote(day - timedelta(days=1), "0"),
            quote(day, "100"),
            quote(day, "10", unit="千克"),
            quote(day - timedelta(days=9), "1"),
        ],
        day,
    )
    assert not alerts


def test_price_warning_severity_and_downward_streak():
    day = date(2026, 10, 11)
    alerts, trends = analyze_prices(
        [
            quote(day - timedelta(days=2), "100"),
            quote(day - timedelta(days=1), "94"),
            quote(day, "80"),
        ],
        day,
    )
    assert alerts[0].severity == "red" and alerts[1].severity == "yellow"
    assert trends[0].direction == "down" and trends[0].consecutive_moves == 2


def test_policy_themes_and_event_authority_freshness_weights():
    assert policy_themes("Export restrictions and a new carbon emissions tax") == [
        "环保",
        "出口限制",
        "税收",
    ]
    assert importance_score(5, 10, 0) == 8
    assert importance_score(5, 10, 8) == 5
    assert importance_score(5, 8, 0) < importance_score(5, 10, 0)


def test_beat_uses_local_eight_am_for_all_complete_report_schedules():
    from app.tasks.celery_app import celery_app

    assert celery_app.conf.timezone == "Asia/Shanghai"
    for name in ("daily-brief", "weekly-brief", "monthly-brief"):
        schedule = celery_app.conf.beat_schedule[name]["schedule"]
        assert schedule.hour == {8} and schedule.minute == {0}
    assert celery_app.conf.beat_schedule["weekly-brief"]["schedule"].day_of_week == {1}
    assert celery_app.conf.beat_schedule["monthly-brief"]["schedule"].day_of_month == {
        1
    }


async def test_changed_evidence_requests_a_scheduled_report_retry(monkeypatch):
    from app.tasks import reports

    async def changed_report(kind):
        return {"status": "stale", "kind": kind}

    monkeypatch.setattr(reports, "build_report", changed_report)
    with pytest.raises(RuntimeError, match="evidence changed"):
        await reports.scheduled_report("daily")
