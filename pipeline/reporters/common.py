"""Evidence-grounded, repeatable reports for complete Shanghai calendar periods."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.core.cache import invalidate_public_cache
from app.core.config import get_settings
from app.core.db import SessionFactory
from app.models import Article, PriceRecord, Report
from app.services.article_service import public_conditions
from app.services.digest_service import (
    Kind,
    evidence_hash,
    get_digest,
    period_bounds,
    summarize_digest,
)
from pipeline.analyzers.event_ranker import rank_events
from pipeline.analyzers.hot_detector import hot_minerals
from pipeline.analyzers.policy_tracker import track_policies
from pipeline.analyzers.price_analyzer import analyze_prices

logger = structlog.get_logger()


def previous_period(
    kind: Kind, now: datetime | None = None
) -> tuple[datetime, datetime]:
    """Return yesterday, previous Monday–Monday, or the previous calendar month."""
    current_start, _ = period_bounds(kind, now)
    if kind == "daily":
        start = current_start - timedelta(days=1)
    elif kind == "weekly":
        start = current_start - timedelta(days=7)
    else:
        start = (current_start - timedelta(days=1)).replace(day=1)
    return start, current_start


async def build_report(kind: Kind, now: datetime | None = None) -> dict:
    """Build a validated snapshot; do not hold a transaction during LLM work."""
    start, end = previous_period(kind, now)
    async with SessionFactory() as db:
        snapshot = await get_digest(db, kind, (start, end))
        if (
            snapshot.id
            and snapshot.scheduled
            and (
                snapshot.mode == "llm"
                or not snapshot.sources
                or not get_settings().LLM_API_KEY.get_secret_value()
            )
        ):
            return {"status": "unchanged", "report_id": str(snapshot.id), "kind": kind}
        signals = await hot_minerals(db, "24h" if kind == "daily" else "7d", end)
        policies = await track_policies(db, start, end)
        events = await rank_events(db, end, persist=False, since=start)
        events = [
            x
            for x in events
            if start <= datetime.fromisoformat(x["last_updated_at"]) < end
        ][:10]
        prices = list(
            (
                await db.scalars(
                    select(PriceRecord).where(
                        PriceRecord.date >= start.date() - timedelta(days=14),
                        PriceRecord.date < end.date(),
                        ~PriceRecord.source.startswith(
                            "https://example.com/miningintel-demo/"
                        ),
                    )
                )
            ).all()
        )
        alerts = {}
        for i in range((end.date() - start.date()).days):
            day = start.date() + timedelta(days=i)
            daily, _ = analyze_prices(prices, day, get_settings().PRICE_ALERT_THRESHOLD)
            for alert in daily:
                if alert.date == day:
                    alerts[str(alert.id)] = alert.model_dump(mode="json")
        _, price_trends = analyze_prices(
            prices, end.date() - timedelta(days=1), get_settings().PRICE_ALERT_THRESHOLD
        )
        coverage = dict(
            (
                await db.execute(
                    select(
                        func.date_trunc(
                            "day",
                            func.timezone(
                                get_settings().DIGEST_TIMEZONE, Article.published_at
                            ),
                        ).label("day"),
                        func.count(),
                    )
                    .where(
                        *public_conditions(),
                        Article.published_at >= start,
                        Article.published_at < end,
                    )
                    .group_by("day")
                    .order_by("day")
                )
            ).all()
        )
    snapshot.analysis = {
        "hot_minerals": [
            {"mineral": name, "count": count}
            for name, count in sorted(
                snapshot.stats.minerals.items(), key=lambda x: (-x[1], x[0])
            )[:5]
        ],
        "hot_signals": [x.model_dump(mode="json") for x in signals[:5]],
        "policies": [x.model_dump(mode="json") for x in policies],
        "price_alerts": sorted(
            alerts.values(), key=lambda x: (x["date"], x["mineral"]), reverse=True
        ),
        "price_trends": [x.model_dump(mode="json") for x in price_trends],
        "price_series": [
            {
                "id": str(x.id),
                "date": x.date.isoformat(),
                "price": str(x.price),
                "mineral": x.mineral,
                "product": x.product,
                "source": x.source,
                "unit": x.unit,
                "currency": x.currency,
                "price_type": x.price_type,
                "source_url": x.source_url,
                "change_pct": str(x.change_pct) if x.change_pct is not None else None,
            }
            for x in sorted(prices, key=lambda x: (x.date, x.source))
            if x.date >= start.date()
        ],
        "events": events,
        "coverage_by_day": [
            {
                "date": (start.date() + timedelta(days=i)).isoformat(),
                "count": coverage.get(
                    datetime.combine(start.date() + timedelta(days=i), time.min), 0
                ),
            }
            for i in range((end.date() - start.date()).days)
        ],
    }
    if snapshot.sources and get_settings().LLM_API_KEY.get_secret_value():
        try:
            snapshot.content = await summarize_digest(snapshot)
            snapshot.mode = "llm"
        except Exception as exc:
            # Keep verified extracts available when the provider or numeric guard fails.
            logger.warning(
                "report_summary_fallback", kind=kind, error_type=type(exc).__name__
            )
    snapshot.scheduled = True
    snapshot.generated_at = datetime.now(UTC)
    async with SessionFactory.begin() as db:
        current = await get_digest(db, kind, (start, end))
        if (
            evidence_hash(current.sources) != evidence_hash(snapshot.sources)
            or current.coverage_hash != snapshot.coverage_hash
        ):
            return {"status": "stale", "kind": kind}
        values = {
            "kind": kind,
            "period_start": start.date(),
            "period_end": end.date(),
            "title": snapshot.title,
            "content": snapshot.content,
            "sources_json": [x.model_dump(mode="json") for x in snapshot.sources],
            "evidence_hash": evidence_hash(snapshot.sources),
            "mode": snapshot.mode,
            "data_json": snapshot.model_dump(mode="json", exclude={"id"}),
            "scheduled": True,
            "created_at": snapshot.generated_at,
        }
        report_id = await db.scalar(
            insert(Report)
            .values(**values)
            .on_conflict_do_update(
                constraint="uq_report_period",
                set_=values,
                where=(Report.evidence_hash.is_distinct_from(values["evidence_hash"]))
                | Report.mode.is_distinct_from(snapshot.mode)
                | Report.data_json["coverage_hash"].astext.is_distinct_from(
                    snapshot.coverage_hash
                )
                | Report.scheduled.is_(False),
            )
            .returning(Report.id)
        )
        if report_id is None:
            report_id = await db.scalar(
                select(Report.id).where(
                    Report.kind == kind,
                    Report.period_start == start.date(),
                    Report.period_end == end.date(),
                )
            )
    await invalidate_public_cache()
    logger.info(
        "report_generated",
        kind=kind,
        report_id=str(report_id),
        period_start=str(start.date()),
        articles=snapshot.stats.article_count,
        mode=snapshot.mode,
    )
    return {
        "status": "succeeded",
        "report_id": str(report_id),
        "kind": kind,
        "articles": snapshot.stats.article_count,
        "mode": snapshot.mode,
    }


def report_bounds(start: date, end: date) -> tuple[datetime, datetime]:
    """Restore exclusive-end calendar boundaries from persisted report dates."""
    zone = ZoneInfo(get_settings().DIGEST_TIMEZONE)
    return datetime.combine(start, time.min, zone), datetime.combine(
        end, time.min, zone
    )
