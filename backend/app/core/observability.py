"""Real database gauges and full consultation latency, including SSE generation."""

import time
from contextlib import asynccontextmanager

from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest
from prometheus_client.core import GaugeMetricFamily
from sqlalchemy import func, select

from app.core.db import SessionFactory
from app.models import Article, Source

CHAT_REQUESTS = Counter(
    "miningintel_chat_requests", "Completed consultations", ["outcome"]
)
CHAT_LATENCY = Histogram(
    "miningintel_chat_duration_seconds",
    "Full verified answer generation",
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300),
)
BOOT_TIME = time.time()


@asynccontextmanager
async def consultation():
    """Measure through verified answer persistence rather than SSE headers."""
    started = time.monotonic()
    outcome = "success"
    try:
        yield
    except BaseException as exc:
        outcome = "cancelled" if type(exc).__name__ == "CancelledError" else "error"
        raise
    finally:
        CHAT_REQUESTS.labels(outcome).inc()
        CHAT_LATENCY.observe(time.monotonic() - started)


async def database_metrics() -> bytes:
    """Export durable ingestion freshness and per-source failures across restarts."""
    async with SessionFactory() as db:
        last = await db.scalar(select(func.max(Article.fetched_at)))
        sources = (
            await db.execute(
                select(Source.name, Source.failure_count).where(Source.active.is_(True))
            )
        ).all()
        distribution = (
            await db.execute(
                select(Article.status, func.count()).group_by(Article.status)
            )
        ).all()
        minerals = (
            await db.execute(
                select(func.unnest(Article.minerals).label("mineral"), func.count())
                .where(Article.status == "published")
                .group_by("mineral")
            )
        ).all()
    values = []
    failure = GaugeMetricFamily(
        "miningintel_source_consecutive_failures",
        "Durable failure streak",
        labels=["source"],
    )
    for name, count in sources:
        failure.add_metric([name], count)
    values.append(failure)
    for name, doc, value in (
        (
            "miningintel_last_article_insert_timestamp_seconds",
            "Latest durable raw article",
            last.timestamp() if last else BOOT_TIME,
        ),
        ("miningintel_active_sources", "Active source count", len(sources)),
    ):
        family = GaugeMetricFamily(name, doc)
        family.add_metric([], value)
        values.append(family)
    family = GaugeMetricFamily(
        "miningintel_articles", "Durable articles by status", labels=["status"]
    )
    for status, count in distribution:
        family.add_metric([status], count)
    values.append(family)
    family = GaugeMetricFamily(
        "miningintel_mineral_articles", "Published mineral coverage", labels=["mineral"]
    )
    for mineral, count in minerals:
        family.add_metric([mineral], count)
    values.append(family)

    class Snapshot:
        def collect(self):
            yield from values

    registry = CollectorRegistry()
    registry.register(Snapshot())
    return generate_latest(registry)
