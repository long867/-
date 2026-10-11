"""Shared test utilities; PostgreSQL tests are opt-in outside CI."""

import os

import pytest


@pytest.fixture(autouse=True)
def isolated_external_services(monkeypatch):
    """Tests never spend live model credits or deliver to configured real recipients."""
    from app.core.config import get_settings

    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("ML_ENABLED", "false")
    monkeypatch.setenv("EMAIL_NOTIFICATIONS_ENABLED", "false")
    monkeypatch.setenv("WEBHOOK_NOTIFICATIONS_ENABLED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Skip integration tests unless their database is explicitly provided."""
    if not os.getenv("TEST_DATABASE_URL"):
        marker = pytest.mark.skip(
            reason="Set TEST_DATABASE_URL for PostgreSQL integration"
        )
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(marker)
