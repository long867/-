"""Typed source configurations and original collector evidence."""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Category = Literal["news", "price", "policy", "report", "company"]


class SourceDefinition(BaseModel):
    """Catalog entry; credentials are referenced by environment variable names."""

    name: str = Field(min_length=1, max_length=200)
    url: str
    type: Literal["rss", "web", "api"]
    category: Category
    region: str | None = None
    language: str = "en"
    authority_score: int = Field(ge=1, le=10)
    fetch_interval: int = Field(default=900, ge=60)
    active: bool = False
    parser_config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("url")
    @classmethod
    def public_scheme(cls, value: str) -> str:
        """Reject credentials and unsupported schemes before collection."""
        from pipeline.fetchers.http import canonical_url

        return canonical_url(value)

    @field_validator("parser_config")
    @classmethod
    def bounded_config(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Reject unbounded request budgets and unsupported pagination at startup."""
        items = int(value.get("max_items", 10))
        interval = float(value.get("min_interval", 1))
        pages = int(value.get("pagination", {}).get("max_pages", 5))
        if not 1 <= items <= 5000 or not 1 <= interval <= 120 or not 1 <= pages <= 50:
            raise ValueError("Collector item/page/interval limits are out of bounds")
        mode = value.get("pagination", {}).get("mode", "none")
        if mode not in {"none", "page", "cursor", "next_url"}:
            raise ValueError("Unsupported pagination mode")
        return value


class RawArticle(BaseModel):
    """Original evidence; unknown publication dates remain unknown."""

    source_name: str
    url: str
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    published_at: datetime | None = None
    language: str
    category: Category
    summary: str | None = None
    raw_json: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title", "content")
    @classmethod
    def nonblank_evidence(cls, value: str) -> str:
        """Reject whitespace-only records without altering original evidence spans."""
        if not value.strip():
            raise ValueError("Original title/content cannot be blank")
        return value

    @field_validator("published_at")
    @classmethod
    def utc_timestamp(cls, value: datetime | None) -> datetime | None:
        """Normalize naive provider dates explicitly to UTC."""
        if value is None:
            return None
        return (
            value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        )


class FetchResult(BaseModel):
    """A checkpoint is committed only after the complete batch is stored."""

    articles: list[RawArticle] = Field(default_factory=list)
    prices: list[dict[str, Any]] = Field(default_factory=list)
    etag: str | None = None
    last_modified: str | None = None
    not_modified: bool = False
    errors: list[str] = Field(default_factory=list)
    state: dict[str, Any] = Field(default_factory=dict)
