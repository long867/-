"""Bounded, credential-free Redis history shared by API, Beat and workers."""

import json
import time
from datetime import UTC, datetime
from typing import Any

import redis
import structlog

from app.core.config import get_settings

PREFIX = "miningintel:tasks:"
INDEX = PREFIX + "recent"


def client() -> redis.Redis:
    """Use short timeouts: history outages must not fail business tasks."""
    return redis.Redis.from_url(
        get_settings().REDIS_URL,
        socket_connect_timeout=1,
        socket_timeout=1,
        decode_responses=True,
    )


def record(task_id: str, name: str, state: str, **fields: Any) -> None:
    """Persist allowlisted metadata only; never retain args, results or exceptions."""
    if not name.startswith("miningintel.") or not task_id:
        return
    allowed = {"queue", "worker", "retries", "error_type", "duration_seconds"}
    values = {key: str(value)[:150] for key, value in fields.items() if key in allowed}
    stamp = datetime.now(UTC).isoformat()
    values.update(task_id=task_id, name=name, state=state, updated_at=stamp)
    timestamp_field = {
        "QUEUED": "queued_at",
        "STARTED": "started_at",
        "SUCCESS": "finished_at",
        "FAILURE": "finished_at",
        "REVOKED": "finished_at",
    }.get(state)
    if timestamp_field:
        values[timestamp_field] = stamp
    connection = client()
    try:
        settings = get_settings()
        pipe = connection.pipeline()
        # A very fast worker can finish before the producer sees publish completion.
        if state == "QUEUED":
            script = """
            if redis.call('HEXISTS', KEYS[1], 'state') == 0 then
                for i=1,#ARGV,2 do redis.call('HSET',KEYS[1],ARGV[i],ARGV[i+1]) end
            end
            """
            pipe.eval(script, 1, PREFIX + task_id, *sum(values.items(), ()))
        else:
            pipe.hset(PREFIX + task_id, mapping=values)
        pipe.expire(PREFIX + task_id, settings.TASK_HISTORY_DAYS * 86400)
        pipe.zadd(INDEX, {task_id: time.time()})
        pipe.zremrangebyscore(
            INDEX, "-inf", time.time() - settings.TASK_HISTORY_DAYS * 86400
        )
        pipe.zremrangebyrank(INDEX, 0, -settings.TASK_HISTORY_LIMIT - 1)
        pipe.execute()
    except redis.RedisError:
        structlog.get_logger().warning("task_history_unavailable")
    finally:
        connection.close()


def history(page: int, page_size: int, state: str | None = None) -> dict:
    """Read a bounded recent window; only admins may expose these records."""
    connection = client()
    try:
        ids = connection.zrevrange(INDEX, 0, get_settings().TASK_HISTORY_LIMIT - 1)
        pipe = connection.pipeline()
        for task_id in ids:
            pipe.hgetall(PREFIX + task_id)
        rows = [
            row
            for row in pipe.execute()
            if row and (not state or row.get("state") == state)
        ]
        offset = (page - 1) * page_size
        return {
            "items": rows[offset : offset + page_size],
            "total": len(rows),
            "page": page,
            "page_size": page_size,
        }
    finally:
        connection.close()


def snapshot(task_id: str) -> dict | None:
    """Return a known task instead of confusing unknown IDs with pending work."""
    connection = client()
    try:
        return connection.hgetall(PREFIX + task_id) or None
    finally:
        connection.close()


def record_http(status: int, elapsed: float) -> None:
    """Maintain expiring minute buckets for the administrator's five-minute rate."""
    connection = client()
    try:
        key = "miningintel:ops:http:" + str(int(time.time() // 60))
        pipe = connection.pipeline()
        pipe.hincrby(key, "requests", 1)
        pipe.hincrby(key, "errors", int(status >= 500))
        pipe.expire(key, 600)
        pipe.execute()
    except redis.RedisError:
        pass
    finally:
        connection.close()


def store_trends(data: dict) -> None:
    """Keep the latest completed analysis for operators, without raw article text."""
    connection = client()
    try:
        connection.set("miningintel:ops:trend", json.dumps(data), ex=86400)
    finally:
        connection.close()
