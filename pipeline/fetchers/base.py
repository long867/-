"""Collector contract, language detection and provider timestamp helpers."""

import asyncio
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from bs4 import BeautifulSoup
from dateutil.parser import parse
from langdetect import DetectorFactory, LangDetectException, detect

from pipeline.fetchers.transport import FetchTransport
from pipeline.schemas import FetchResult, RawArticle, SourceDefinition

DetectorFactory.seed = 0


def timestamp(value: Any) -> datetime | None:
    """Parse ISO/RFC dates and Unix epochs without inventing missing dates."""
    if value is None or value == "":
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, UTC)
        result = parse(str(value))
        return (
            result.replace(tzinfo=UTC)
            if result.tzinfo is None
            else result.astimezone(UTC)
        )
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def plain_text(html: str) -> str:
    """Convert feed markup to evidence, excluding scripts and styles."""
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style"]):
        element.decompose()
    return soup.get_text(" ", strip=True)


def detect_language(text: str, fallback: str) -> str:
    """Use deterministic detection and configured language for short snippets."""
    if len(text.strip()) < 40:
        return fallback
    try:
        return detect(text[:5000])
    except LangDetectException:
        return fallback


class BaseFetcher(ABC):
    """Reusable transport and checkpoint for a single source run."""

    def __init__(
        self,
        source: SourceDefinition,
        transport: FetchTransport | None = None,
        *,
        etag: str | None = None,
        last_modified: str | None = None,
        state: dict[str, Any] | None = None,
    ) -> None:
        self.source = source
        self.config = source.parser_config
        self.transport = transport or FetchTransport(self.config)
        self.result = FetchResult(state=dict(state or {}))
        self.headers: dict[str, str] = {}
        if etag:
            self.headers["If-None-Match"] = etag
        if last_modified:
            self.headers["If-Modified-Since"] = last_modified

    @abstractmethod
    async def fetch(self) -> list[RawArticle]:
        """Collect articles and populate the batch checkpoint."""

    async def article(self, **values: Any) -> RawArticle:
        """Build a validated article with automatic language detection."""
        language = await asyncio.to_thread(
            detect_language,
            values["title"] + "\n" + values["content"],
            self.source.language,
        )
        return RawArticle(
            source_name=self.source.name,
            language=language,
            category=self.source.category,
            **values,
        )

    def checkpoint(self, response: Any) -> bool:
        """Record validators; 304 preserves previously committed validators."""
        if response.status_code == 304:
            self.result.not_modified = True
            return False
        response.raise_for_status()
        self.result.etag = response.headers.get("etag")
        self.result.last_modified = response.headers.get("last-modified")
        return True
