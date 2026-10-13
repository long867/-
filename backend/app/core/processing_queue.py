"""Redis leases prevent repeated scans from duplicating queued article work."""

from uuid import UUID

import redis

from app.core.config import get_settings

LEASE_PREFIX = "miningintel:queued:article:"
LEASE_SECONDS = 86400
CLAIM = """
if redis.call('EXISTS', KEYS[2]) == 1 then return 0 end
local previous = redis.call('GET', KEYS[1])
if previous then
    local state = redis.call('HGET', ARGV[3] .. previous, 'state')
    if state == 'SUCCESS' or state == 'FAILURE' or state == 'REVOKED' then
        redis.call('DEL', KEYS[1])
    end
end
if redis.call('SET', KEYS[1], ARGV[1], 'NX', 'EX', ARGV[2]) then return 1 end
return 0
"""
RELEASE = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""


def connection() -> redis.Redis:
    """Bound queue coordination calls without retaining a global socket pool."""
    return redis.Redis.from_url(
        get_settings().REDIS_URL, socket_connect_timeout=1, socket_timeout=1
    )


def claim(article_id: str, task_id: str) -> bool:
    """Reserve queued and retried work; expired/lost leases remain recoverable."""
    article_id = str(UUID(article_id))
    client = connection()
    try:
        return bool(
            client.eval(
                CLAIM,
                2,
                LEASE_PREFIX + article_id,
                "process:" + article_id,
                task_id,
                LEASE_SECONDS,
                "miningintel:tasks:",
            )
        )
    finally:
        client.close()


def release(article_id: str, task_id: str) -> None:
    """Only the owning task may release a lease, protecting newer dispatches."""
    article_id = str(UUID(article_id))
    client = connection()
    try:
        client.eval(RELEASE, 1, LEASE_PREFIX + article_id, task_id)
    finally:
        client.close()
