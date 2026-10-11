"""Collection request bounds, redirect validation and source schemas."""

from unittest.mock import AsyncMock

import httpx
import pytest
import respx
from app.core.config import Settings

from pipeline.fetchers.http import safe_get, validate_public_url


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://10.0.0.1/",
    ],
)
async def test_private_destinations_rejected(url: str) -> None:
    with pytest.raises(ValueError):
        await validate_public_url(url)


@respx.mock
async def test_redirect_destinations_revalidated(monkeypatch) -> None:
    import pipeline.fetchers.http as module

    calls = []

    async def validate(url: str) -> None:
        calls.append(url)
        if "127.0.0.1" in url:
            raise ValueError("private")

    monkeypatch.setattr(module, "validate_public_url", validate)
    respx.get("https://public.example/").mock(
        return_value=httpx.Response(302, headers={"location": "http://127.0.0.1/"})
    )
    with pytest.raises(ValueError):
        await safe_get("https://public.example/")
    assert calls == ["https://public.example/", "http://127.0.0.1/"]


@respx.mock
async def test_fetch_size_limit(monkeypatch) -> None:
    import pipeline.fetchers.http as module

    monkeypatch.setattr(module, "validate_public_url", AsyncMock())
    monkeypatch.setattr(
        module, "get_settings", lambda: Settings(FETCH_MAX_BYTES=1024, _env_file=None)
    )
    respx.get("https://public.example/").mock(
        return_value=httpx.Response(200, content=b"x" * 2048)
    )
    with pytest.raises(ValueError, match="FETCH_MAX_BYTES"):
        await safe_get("https://public.example/")


async def test_conditional_feed_304(monkeypatch) -> None:
    from pipeline.fetchers.rss_fetcher import RSSFetcher
    from pipeline.fetchers.transport import FetchTransport
    from pipeline.schemas import SourceDefinition

    fetch = AsyncMock(return_value=httpx.Response(304))
    monkeypatch.setattr(FetchTransport, "get", fetch)
    source = SourceDefinition(
        name="Feed",
        url="https://example.com/feed",
        type="rss",
        category="news",
        authority_score=8,
    )
    collector = RSSFetcher(source, etag='"v1"')
    assert await collector.fetch() == []
    assert collector.result.not_modified
    fetch.assert_awaited_once_with(source.url, {"If-None-Match": '"v1"'})


async def test_price_api_mapping(monkeypatch) -> None:
    from pipeline.fetchers.api_fetcher import APIFetcher
    from pipeline.fetchers.transport import FetchTransport
    from pipeline.schemas import SourceDefinition

    response = httpx.Response(
        200,
        request=httpx.Request("GET", "https://example.com/prices"),
        json={
            "data": [
                {
                    "symbol": "铜",
                    "value": "9120.25",
                    "unit": "吨",
                    "currency": "USD",
                    "date": "2026-10-10",
                }
            ]
        },
    )
    monkeypatch.setattr(FetchTransport, "get", AsyncMock(return_value=response))
    source = SourceDefinition(
        name="Price API",
        url="https://example.com/prices",
        authority_score=8,
        type="api",
        category="price",
        parser_config={
            "records_path": "data",
            "fields": {"mineral": "symbol", "price": "value"},
        },
    )
    collector = APIFetcher(source)
    await collector.fetch()
    batch = collector.result
    assert batch.prices[0]["mineral"] == "铜"
    assert batch.prices[0]["source"] == source.url
    assert batch.articles[0].content == response.text
