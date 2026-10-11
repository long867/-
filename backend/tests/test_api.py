"""Application smoke tests and authentication boundaries without external services."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from app.api.routes import events
from app.core.db import get_db
from app.main import app
from app.models import Event


async def test_liveness_and_openapi() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/health/live")
        assert response.status_code == 200
        assert response.json()["retrieval_mode"] in {"keyword", "hybrid"}
        assert response.headers["x-request-id"]
        schema = (await client.get("/openapi.json")).json()
        assert "/api/v1/chat" in schema["paths"]
        assert "HTTPBearer" in schema["components"]["securitySchemes"]


async def test_admin_without_credentials_is_denied() -> None:
    async def fake_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = fake_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/admin/sources")
            assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()


async def test_sensitive_inputs_not_echoed_in_errors(monkeypatch) -> None:
    import app.main as module

    monkeypatch.setattr(module, "limited", AsyncMock(return_value=False))

    async def fake_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = fake_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/v1/auth/register", json={"email": "invalid", "password": "leak"}
            )
            assert response.status_code == 422
            assert "leak" not in response.text
            assert all("input" not in error for error in response.json()["detail"])
    finally:
        app.dependency_overrides.clear()


async def test_cors_is_restricted() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.options(
            "/api/v1/articles",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert (
            response.headers["access-control-allow-origin"] == "http://localhost:3000"
        )
        forbidden = await client.options(
            "/api/v1/articles",
            headers={
                "Origin": "https://untrusted.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" not in forbidden.headers


async def test_event_response_does_not_leak_unpublished_summary() -> None:
    event = Event(
        id=uuid4(),
        title_zh="PRIVATE TITLE",
        summary_zh="PRIVATE SUMMARY",
        first_seen_at=datetime.now(UTC),
        last_updated_at=datetime.now(UTC),
        article_count=20,
        minerals=["private mineral"],
        regions=["private region"],
        importance_score=99,
    )
    published = SimpleNamespace(
        title="Published title",
        title_zh=None,
        summary="Published summary",
        summary_zh=None,
        minerals=["铜"],
        regions=["智利"],
        quality_score=80,
        relevance_score=90,
    )
    db = SimpleNamespace(
        execute=AsyncMock(
            return_value=SimpleNamespace(all=lambda: [(event, 1, published)])
        )
    )
    result = await events(db, limit=30)
    assert result[0].title_zh == "Published title"
    assert result[0].summary_zh == "Published summary"
    assert result[0].article_count == 1
    assert result[0].minerals == ["铜"]
    assert "PRIVATE" not in result[0].model_dump_json()
