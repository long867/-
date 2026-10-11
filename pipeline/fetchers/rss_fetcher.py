"""RSS/Atom conditional collection with full-text enrichment when allowed."""

import asyncio
from urllib.parse import urljoin

import feedparser
import httpx
import trafilatura

from pipeline.fetchers.base import BaseFetcher, plain_text, timestamp
from pipeline.fetchers.http import canonical_url
from pipeline.schemas import RawArticle


class RSSFetcher(BaseFetcher):
    async def fetch(self) -> list[RawArticle]:
        """Read a feed and retain validators for a completely parsed batch."""
        response = await self.transport.get(self.source.url, self.headers)
        if not self.checkpoint(response):
            return []
        feed = await asyncio.to_thread(feedparser.parse, response.content)
        if not feed.entries and feed.bozo:
            raise ValueError("Invalid RSS/Atom response")
        articles: list[RawArticle] = []
        limit = min(max(int(self.config.get("max_items", 20)), 1), 100)
        for entry in feed.entries[:limit]:
            try:
                if not entry.get("link"):
                    continue
                url = canonical_url(urljoin(str(response.url), entry.link))
                markup = entry.get("summary", "")
                if entry.get("content"):
                    markup = entry.content[0].get("value", markup)
                content = plain_text(markup)
                full_text = False
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
                            },
                        )
                    )
            except (ValueError, TypeError, KeyError) as exc:
                self.result.errors.append("rss_entry:" + type(exc).__name__)
        self.result.articles = articles
        return articles
