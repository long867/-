"""Database-backed system counts and bounded Redis infrastructure snapshots."""

import asyncio
import time
from datetime import UTC, datetime
from datetime import time as day_time
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.task_history import client
from app.models import Article, ChatMessage, Source
from app.schemas.operations import SystemMetrics


def runtime_snapshot() -> dict:
    """Read recent counters and expiring heartbeats, never sensitive broker bodies."""
    connection = client()
    try:
        minute = int(time.time() // 60)
        buckets = [
            connection.hgetall(f"miningintel:ops:http:{minute - i}") for i in range(5)
        ]
        requests = sum(int(row.get("requests", 0)) for row in buckets)
        errors = sum(int(row.get("errors", 0)) for row in buckets)
        workers = [
            key.removeprefix("miningintel:ops:worker:")
            for key in connection.scan_iter("miningintel:ops:worker:*", count=100)
        ]
        return {
            "requests_5m": requests,
            "errors_5m": errors,
            "error_rate_5m": errors / requests if requests else 0,
            "workers": workers,
            "beat_alive": bool(connection.exists("miningintel:ops:beat-heartbeat")),
            "queues": {queue: connection.llen(queue) for queue in ()},
        }
    finally:
        connection.close()


async def system_metrics(db: AsyncSession) -> SystemMetrics:
    """Count today's ingestion and consultations in the configured calendar zone."""
    local = datetime.now(ZoneInfo(get_settings().DIGEST_TIMEZONE))
    start = datetime.combine(local.date(), day_time(), local.tzinfo).astimezone(UTC)
    articles = (
        await db.execute(
            select(
                func.count(Article.id),
                func.count().filter(Article.status == "published"),
                func.count().filter(Article.fetched_at >= start),
                func.count().filter(Article.status == "pending"),
            )
        )
    ).one()
    chats = (
        await db.execute(
            select(
                func.count(ChatMessage.id),
                func.count().filter(ChatMessage.created_at >= start),
            )
        )
    ).one()
    sources = (
        await db.execute(
            select(
                func.count().filter(Source.active.is_(True)),
                func.count().filter(Source.active.is_(True), Source.failure_count >= 3),
            ).select_from(Source)
        )
    ).one()
    runtime = await asyncio.to_thread(runtime_snapshot)

    # Broker queues reside in a different Redis database from history/cache.
    def queues() -> dict:
        import redis

        connection = redis.Redis.from_url(
            get_settings().CELERY_BROKER_URL, socket_connect_timeout=1, socket_timeout=1
        )
        try:
            return {
                name: connection.llen(name) for name in ("celery", "nlp", "insights")
            }
        finally:
            connection.close()

    runtime["queues"] = await asyncio.to_thread(queues)
    return SystemMetrics(
        articles_total=articles[0],
        articles_published=articles[1],
        articles_today=articles[2],
        pending_articles=articles[3],
        chat_total=chats[0],
        chat_today=chats[1],
        active_sources=sources[0],
        failing_sources=sources[1],
        **runtime,
    )
