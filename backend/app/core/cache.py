"""Shared Redis JSON caching with explicit TTLs, invalidation and degradation."""

import hashlib
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response
from pydantic import TypeAdapter
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings

logger = structlog.get_logger()
VERSION_KEY = "miningintel:public:v3:version"


async def cached[T](
    request: Request,
    response: Response,
    namespace: str,
    parameters: str,
    ttl: int,
    adapter: TypeAdapter[T],
    loader: Callable[[], Awaitable[T]],
) -> T:
    """Cache validated public data; Redis outages retain working database reads."""
    client: Redis = request.app.state.redis
    key: str | None = None
    if get_settings().CACHE_ENABLED:
        try:
            version = await client.get(VERSION_KEY) or b"0"
            suffix = hashlib.sha256(parameters.encode()).hexdigest()[:24]
            key = f"miningintel:public:v3:{version.decode()}:{namespace}:{suffix}"
            raw = await client.get(key)
            if raw:
                result = adapter.validate_json(raw)
                response.headers["X-Cache"] = "HIT"
                response.headers["X-Cache-TTL"] = str(max(0, await client.ttl(key)))
                return result
        except (RedisError, ValueError):
            key = None
            logger.warning("public_cache_unavailable", namespace=namespace)
    result = await loader()
    response.headers["X-Cache"] = "MISS" if key else "BYPASS"
    if key:
        try:
            await client.set(key, adapter.dump_json(result), ex=ttl)
            response.headers["X-Cache-TTL"] = str(ttl)
        except RedisError:
            response.headers["X-Cache"] = "BYPASS"
    return result


async def invalidate_public_cache() -> None:
    """Bump a shared generation after a committed write; old keys expire naturally."""
    if not get_settings().CACHE_ENABLED:
        return
    client = Redis.from_url(
        get_settings().REDIS_URL, socket_connect_timeout=0.3, socket_timeout=0.3
    )
    try:
        await client.incr(VERSION_KEY)
    except RedisError:
        logger.warning("public_cache_invalidation_unavailable")
    finally:
        await client.aclose()
