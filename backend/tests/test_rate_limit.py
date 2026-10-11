"""Development limits remain real limits and cannot weaken production settings."""

import pytest
from app.core.config import Settings
from app.core.rate_limit import build_rate_limit_guard, client_route_key
from app.main import _local_windows, memory_limited
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded


def test_local_limit_resets_and_groups_all_chat_aliases() -> None:
    _local_windows.clear()
    assert all(not memory_limited("test-ip", "chat", 0) for _ in range(10))
    assert memory_limited("test-ip", "chat", 1)
    assert not memory_limited("test-ip", "auth", 1)
    assert not memory_limited("test-ip", "chat", 61)
    _local_windows.clear()


def test_production_rejects_memory_rate_limiter() -> None:
    with pytest.raises(ValueError, match="Redis"):
        Settings(
            APP_ENV="production",
            RATE_LIMIT_BACKEND="memory",
            FETCH_DISTRIBUTED_PACING=True,
            SECRET_KEY="r" * 40,
            _env_file=None,
        )


async def test_nested_router_limits_apply_and_variable_ids_share_one_bucket() -> None:
    limiter = Limiter(key_func=client_route_key, storage_uri="memory://")
    api = FastAPI(dependencies=[Depends(build_rate_limit_guard(limiter, "2/minute"))])
    api.state.limiter = limiter
    inner = APIRouter()

    @inner.get("/articles/{article_id}")
    def article(article_id: int) -> dict:
        return {"id": article_id}

    @inner.get("/events")
    def events() -> list:
        return []

    outer = APIRouter(prefix="/api")
    outer.include_router(inner)
    api.include_router(outer)

    @api.exception_handler(RateLimitExceeded)
    async def exceeded(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse({"detail": "rate limit"}, status_code=429)

    async with AsyncClient(
        transport=ASGITransport(app=api), base_url="http://test"
    ) as client:
        assert (await client.get("/api/articles/1")).status_code == 200
        assert (await client.get("/api/articles/2")).status_code == 200
        assert (await client.get("/api/articles/3")).status_code == 429
        assert (await client.get("/api/events")).status_code == 200
