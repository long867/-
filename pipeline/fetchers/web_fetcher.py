"""Bounded discovery, optional browser rendering and readable body extraction."""

import asyncio
import os
import re
from urllib.parse import urljoin, urlsplit

import httpx
import trafilatura
from bs4 import BeautifulSoup
from playwright.async_api import Route, async_playwright

from pipeline.fetchers.base import BaseFetcher, timestamp
from pipeline.fetchers.http import canonical_url, validate_public_url
from pipeline.fetchers.resolver import public_addresses
from pipeline.schemas import RawArticle


class WebFetcher(BaseFetcher):
    async def render(self, url: str) -> str:
        """Render permitted same-origin documents and validate every browser request."""
        await self.transport.robots(url)
        await self.transport.pace(url)
        origin = urlsplit(url).netloc
        addresses = await public_addresses(urlsplit(url).hostname)
        proxy_url = os.getenv(self.config.get("proxy_env", ""))
        proxy = None
        if proxy_url:
            parsed_proxy = urlsplit(proxy_url)
            proxy = {
                "server": f"{parsed_proxy.scheme}://{parsed_proxy.hostname}:{parsed_proxy.port}"
            }
            if parsed_proxy.username:
                proxy["username"] = parsed_proxy.username
                proxy["password"] = parsed_proxy.password or ""
        async with async_playwright() as api:
            browser = await api.chromium.launch(
                headless=True,
                channel=self.transport.settings.FETCH_BROWSER_CHANNEL
                or self.config.get("browser_channel"),
                proxy=proxy,
                args=[
                    f"--host-resolver-rules=MAP {urlsplit(url).hostname} {addresses[0]}"
                ],
            )
            context = await browser.new_context(
                user_agent=self.transport.settings.USER_AGENT,
                extra_http_headers=self.transport.request_headers(),
            )
            await context.route("**/*", lambda route: self._guard(route, origin))
            try:
                page = await context.new_page()
                response = await page.goto(
                    url, wait_until="domcontentloaded", timeout=30000
                )
                if response is None or response.status >= 400:
                    raise ValueError("Browser navigation failed")
                if selector := self.config.get("wait_for_selector"):
                    await page.wait_for_selector(selector, timeout=15000)
                html = await page.content()
                if len(html.encode()) > self.transport.settings.FETCH_MAX_BYTES:
                    raise ValueError("Rendered response exceeds FETCH_MAX_BYTES")
                return html
            finally:
                await context.unroute_all(behavior="ignoreErrors")
                await browser.close()

    async def _guard(self, route: Route, origin: str) -> None:
        """Block private destinations, external requests and nonessential media."""
        try:
            await validate_public_url(route.request.url)
            if urlsplit(
                route.request.url
            ).netloc != origin or route.request.resource_type in {
                "image",
                "media",
                "font",
                "websocket",
            }:
                await route.abort()
                return
            await self.transport.robots(route.request.url)
            await self.transport.pace(route.request.url)
            await route.continue_()
        except (ValueError, httpx.HTTPError, OSError):
            await route.abort()

    async def parse_page(self, url: str, html: str) -> RawArticle:
        """Extract one article, retaining source title and metadata dates."""
        if selector := self.config.get("content_selector"):
            node = BeautifulSoup(html, "html.parser").select_one(selector)
            body = node.get_text("\n", strip=True) if node else None
        else:
            body = await asyncio.to_thread(
                trafilatura.extract, html, include_tables=True
            )
        metadata = await asyncio.to_thread(trafilatura.extract_metadata, html)
        if not body:
            raise ValueError("No readable article body")
        return await self.article(
            url=canonical_url(url),
            title=metadata.title if metadata and metadata.title else self.source.name,
            content=body,
            published_at=timestamp(metadata.date if metadata else None),
            raw_json={"publisher": metadata.sitename if metadata else None},
        )

    async def fetch(self) -> list[RawArticle]:
        """Discover article links on a listing or extract a configured single page."""
        response = await self.transport.get(self.source.url, self.headers)
        if not self.checkpoint(response):
            return []
        html = (
            await self.render(str(response.url))
            if self.config.get("dynamic")
            else response.text
        )
        selector = self.config.get("link_selector")
        if not selector:
            articles = [await self.parse_page(str(response.url), html)]
        else:
            soup = BeautifulSoup(html, "html.parser")
            links: list[str] = []
            for node in soup.select(selector):
                href = node.get("href")
                if not href:
                    continue
                try:
                    url = canonical_url(urljoin(str(response.url), str(href)))
                except ValueError:
                    continue
                if urlsplit(url).netloc != urlsplit(str(response.url)).netloc:
                    continue
                if pattern := self.config.get("link_pattern"):
                    if not re.search(pattern, url):
                        continue
                if url not in links:
                    links.append(url)
            if not links:
                raise ValueError("Configured listing selector found no article links")
            articles = []
            for url in links[: min(int(self.config.get("max_items", 10)), 100)]:
                try:
                    page = await self.transport.get(url)
                    page.raise_for_status()
                    body = (
                        await self.render(str(page.url))
                        if self.config.get("dynamic")
                        else page.text
                    )
                    articles.append(await self.parse_page(str(page.url), body))
                except (httpx.HTTPError, ValueError, OSError) as exc:
                    self.result.errors.append("web_article:" + type(exc).__name__)
        self.result.articles = articles
        return articles
