"""ORM adapter for Celery tasks and existing integrations."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.models import Source
from pipeline.fetchers.api_fetcher import APIFetcher
from pipeline.fetchers.base import BaseFetcher, timestamp
from pipeline.fetchers.price_fetcher import PPIPriceFetcher
from pipeline.fetchers.rss_fetcher import RSSFetcher
from pipeline.fetchers.web_fetcher import WebFetcher
from pipeline.schemas import SourceDefinition

__all__ = ["Document", "FetchBatch", "collect", "create_fetcher", "timestamp"]


@dataclass
class Document:
    title: str
    content: str
    url: str
    published_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    language: str | None = None


@dataclass
class FetchBatch:
    documents: list[Document]
    etag: str | None = None
    last_modified: str | None = None
    not_modified: bool = False
    prices: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)


def create_fetcher(source: SourceDefinition, **kwargs: Any) -> BaseFetcher:
    """Select a typed adapter."""
    adapters = {"rss": RSSFetcher, "web": WebFetcher, "api": APIFetcher}
    if source.parser_config.get("adapter") in {"ppi_lithium_spot", "ppi_spot_market"}:
        return PPIPriceFetcher(source, **kwargs)
    if source.parser_config.get("adapter") == "sunsirs_mineral_daily":
        from pipeline.fetchers.daily_price_fetcher import DailyPriceFetcher

        return DailyPriceFetcher(source, **kwargs)
    return adapters[source.type](source, **kwargs)


async def collect(source: Source) -> FetchBatch:
    """Collect a detached source without holding a database transaction."""
    definition = SourceDefinition(
        name=source.name,
        url=source.url,
        type=source.type,
        category=source.category,
        region=source.region,
        language=source.language,
        authority_score=source.authority_score,
        fetch_interval=source.fetch_interval,
        active=source.active,
        parser_config=source.config_json,
    )
    fetcher = create_fetcher(
        definition,
        etag=source.etag,
        last_modified=source.last_modified,
        state=source.fetch_state,
    )
    articles = await fetcher.fetch()
    result = fetcher.result
    return FetchBatch(
        documents=[
            Document(
                row.title,
                row.content,
                row.url,
                row.published_at,
                row.raw_json,
                row.language,
            )
            for row in articles
        ],
        etag=result.etag,
        last_modified=result.last_modified,
        not_modified=result.not_modified,
        prices=result.prices,
        errors=result.errors,
        state=result.state,
    )
