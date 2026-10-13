"""RSS/Atom conditional collection with full-text enrichment when allowed."""

import asyncio
from urllib.parse import urljoin

import feedparser
import httpx
import structlog
import trafilatura

from pipeline.fetchers.api_fetcher import query_url
from pipeline.fetchers.base import BaseFetcher, plain_text, timestamp
from pipeline.fetchers.http import canonical_url
from pipeline.schemas import RawArticle


class RSSFetcher(BaseFetcher):
    async def fetch(self) -> list[RawArticle]:
        """Read a feed and retain validators for a completely parsed batch."""
        pagination = self.config.get("pagination", {})
        if pagination.get("mode", "none") not in {"none", "page"}:
            raise ValueError("RSS supports only explicit page pagination")
        start = int(pagination.get("start", 1))
        initial_url = self.source.url
        if pagination.get("mode") == "page" and start != 1:
            initial_url = query_url(
                initial_url, pagination.get("param", "paged"), start
            )
        response = await self.transport.get(initial_url, self.headers)
        if not self.checkpoint(response):
            return []
        articles: list[RawArticle] = []
        self.result.articles = articles
        pages = (
            min(int(pagination.get("max_pages", 1)), 50)
            if pagination.get("mode") == "page"
            else 1
        )
        limit = min(max(int(self.config.get("max_items", 20)), 1), 5000)
        seen: set[str] = set()
        for page in range(pages):
            if page:
                url = query_url(
                    self.source.url,
                    pagination.get("param", "paged"),
                    start + page,
                )
                try:
                    response = await self.transport.get(url)
                    if response.status_code in {404, 410}:
                        break
                    response.raise_for_status()
                except (httpx.HTTPError, ValueError, OSError) as exc:
                    self.result.errors.append("rss_page:" + type(exc).__name__)
                    break
            feed = await asyncio.to_thread(feedparser.parse, response.content)
            if not feed.entries and feed.bozo:
                if page == 0:
                    raise ValueError("Invalid RSS/Atom response")
                self.result.errors.append("rss_page:InvalidFeed")
                break
            entries = []
            for entry in feed.entries:
                link = entry.get("link")
                if link and link not in seen:
                    seen.add(link)
                    entries.append(entry)
            if not entries:
                break
            articles.extend(
                await self.read_entries(
                    entries, str(response.url), limit - len(articles)
                )
            )
            self.result.state["next_page"] = start + page + 1
            if self.config.get("emit_progress"):
                structlog.get_logger().info(
                    "rss_archive_page_complete",
                    source=self.source.name,
                    page=start + page,
                    collected=len(articles),
                )
            if len(articles) >= limit:
                break
        self.result.articles = articles
        return articles

    async def read_entries(
        self, entries: list, base_url: str, limit: int
    ) -> list[RawArticle]:
        """Extract original feed evidence without repeating archive entries."""
        articles: list[RawArticle] = []
        for entry in entries[:limit]:
            try:
                if not entry.get("link"):
                    continue
                url = canonical_url(urljoin(base_url, entry.link))
                markup = entry.get("summary", "")
                if entry.get("content"):
                    markup = entry.content[0].get("value", markup)
                content = plain_text(markup)
                full_text = False
                if self.config.get("require_mineral_match"):
                    from pipeline.processors.entities import extract_entities
                    from pipeline.processors.policy_document import (
                        general_mineral_policy,
                    )

                    title = plain_text(entry.get("title", ""))
                    if not (
                        extract_entities(title + "\n" + content)["minerals"]
                        or general_mineral_policy(self.source, title, content)
                    ):
                        continue
                if self.config.get("fetch_full_content", True):
                    try:
                        page = await self.transport.get(url)
                        page.raise_for_status()
                        extracted = await asyncio.to_thread(
                            trafilatura.extract, page.text, include_tables=True
                        )
                        if extracted:
                            content, full_text = extracted, True
                    except (httpx.HTTPError, ValueError, OSError) as exc:
                        self.result.errors.append("rss_full_text:" + type(exc).__name__)
                if content:
                    articles.append(
                        await self.article(
                            title=plain_text(entry.get("title", "Untitled")),
                            url=url,
                            content=content,
                            summary=plain_text(entry.get("summary", "")) or None,
                            published_at=timestamp(
                                entry.get("published") or entry.get("updated")
                            ),
                            raw_json={
                                "feed_id": str(entry.get("id", "")),
                                "full_text": full_text,
                                "feed_summary": plain_text(markup),
                                "feed_page": base_url,
                            },
                        )
                    )
            except (ValueError, TypeError, KeyError) as exc:
                self.result.errors.append("rss_entry:" + type(exc).__name__)
        return articles
