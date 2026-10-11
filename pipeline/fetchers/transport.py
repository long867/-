"""Public-only bounded HTTP, robots rules, shared pacing and transient retries."""

import asyncio
import hashlib
import os
import random
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx
import redis.asyncio as redis
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt
from tenacity.wait import wait_random_exponential

from app.core.config import get_settings
from pipeline.fetchers.http import canonical_url, validate_public_url
from pipeline.fetchers.resolver import public_addresses


class RobotsDenied(ValueError):
    """The publisher explicitly disallows this collection path."""


class TransientFetchError(httpx.HTTPError):
    """Retryable provider response with an optional bounded retry delay."""

    def __init__(self, status: int, delay: float = 0) -> None:
        super().__init__(f"Retryable HTTP status {status}")
        self.delay = delay


def retry_after(value: str | None) -> float:
    """Parse seconds or HTTP-date, bounded to two minutes per retry."""
    if not value:
        return 0
    try:
        delay = float(value)
    except ValueError:
        try:
            delay = (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds()
        except (ValueError, TypeError, OverflowError):
            return 0
    return max(0, min(delay, 120))


class FetchTransport:
    """One transport per batch; Redis coordinates origins across Celery workers."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.settings = get_settings()
        self._robots: dict[str, tuple[RobotFileParser | None, float]] = {}
        self._next_request: dict[str, float] = {}
        self._mutex = asyncio.Lock()

    def request_headers(self) -> dict[str, str]:
        """Resolve credentials from environment without storing them in evidence."""
        headers = {
            "User-Agent": self.settings.USER_AGENT,
            **self.config.get("headers", {}),
        }
        for header, env_name in self.config.get("headers_env", {}).items():
            value = os.getenv(env_name)
            if not value:
                raise ValueError(f"Missing collector environment variable: {env_name}")
            headers[header] = value
        auth = self.config.get("auth", {})
        if auth:
            value = os.getenv(auth["token_env"])
            if not value:
                raise ValueError("Collector authentication is not configured")
            headers[auth.get("header", "Authorization")] = (
                auth.get("prefix", "Bearer ") + value
            )
        return headers

    async def pace(self, url: str, crawl_delay: float = 0) -> None:
        """Reserve an origin time slot atomically; distributed mode fails closed."""
        origin = urlsplit(url).netloc.lower()
        delay = max(
            random.uniform(1, 3), crawl_delay, self.config.get("min_interval", 1)
        )
        if self.settings.FETCH_DISTRIBUTED_PACING:
            key = "collector:pace:" + hashlib.sha256(origin.encode()).hexdigest()
            client = redis.Redis.from_url(self.settings.REDIS_URL)
            try:
                script = (
                    "local t=redis.call('TIME'); "
                    "local now=t[1]*1000+t[2]/1000; "
                    "local slot=math.max(now,"
                    "tonumber(redis.call('GET',KEYS[1]) or 0)); "
                    "redis.call('SET',KEYS[1],slot+ARGV[1],'PX',ARGV[2]); "
                    "return math.floor(slot-now)"
                )
                wait_ms = await client.eval(script, 1, key, int(delay * 1000), 3600000)
            finally:
                await client.aclose()
            await asyncio.sleep(wait_ms / 1000)
        else:
            async with self._mutex:
                now = time.monotonic()
                slot = max(now, self._next_request.get(origin, now))
                self._next_request[origin] = slot + delay
            await asyncio.sleep(max(0, slot - now))

    async def _request(
        self, url: str, headers: dict[str, str], *, obey_robots: bool
    ) -> httpx.Response:
        current = canonical_url(url)
        proxy = os.getenv(self.config.get("proxy_env", "")) or None
        async with httpx.AsyncClient(
            timeout=self.settings.FETCH_TIMEOUT, proxy=proxy, trust_env=False
        ) as client:
            for _ in range(6):
                await validate_public_url(current)
                parts = urlsplit(current)
                addresses = await public_addresses(parts.hostname)
                address = addresses[0]
                netloc = f"[{address}]" if ":" in address else address
                if parts.port:
                    netloc += f":{parts.port}"
                destination = urlunsplit(
                    (parts.scheme, netloc, parts.path, parts.query, "")
                )
                crawl_delay = await self.robots(current) if obey_robots else 0
                await self.pace(current, crawl_delay)
                # Pin the checked IP while retaining the origin Host and TLS identity.
                async with client.stream(
                    "GET",
                    destination,
                    headers=headers | {"Host": parts.netloc},
                    extensions={"sni_hostname": parts.hostname},
                ) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        target = canonical_url(
                            urljoin(current, response.headers["location"])
                        )
                        if (
                            parts.scheme == "https"
                            and urlsplit(target).scheme == "http"
                        ):
                            raise ValueError("HTTPS downgrade redirects are forbidden")
                        if (urlsplit(target).scheme, urlsplit(target).netloc) != (
                            parts.scheme,
                            parts.netloc,
                        ):
                            headers = {"User-Agent": self.settings.USER_AGENT}
                        current = target
                        continue
                    if response.status_code in {429, 500, 502, 503, 504}:
                        raise TransientFetchError(
                            response.status_code,
                            retry_after(response.headers.get("retry-after")),
                        )
                    chunks: list[bytes] = []
                    size = 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > self.settings.FETCH_MAX_BYTES:
                            raise ValueError("Response exceeds FETCH_MAX_BYTES")
                        chunks.append(chunk)
                    return httpx.Response(
                        response.status_code,
                        headers={
                            key: value
                            for key, value in response.headers.items()
                            if key not in {"content-encoding", "content-length"}
                        },
                        content=b"".join(chunks),
                        request=httpx.Request("GET", current),
                    )
        raise ValueError("Too many redirects")

    async def get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        *,
        obey_robots: bool = True,
    ) -> httpx.Response:
        """Retry transport failures, 429 and selected 5xx; never retry 401/403."""
        exponential = wait_random_exponential(multiplier=1, max=30)

        def wait(retry_state: Any) -> float:
            error = retry_state.outcome.exception()
            return max(exponential(retry_state), getattr(error, "delay", 0))

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self.settings.FETCH_RETRIES),
            retry=retry_if_exception_type((httpx.TransportError, TransientFetchError)),
            wait=wait,
            reraise=True,
        ):
            with attempt:
                return await self._request(
                    url,
                    self.request_headers() | (headers or {}),
                    obey_robots=obey_robots,
                )
        raise RuntimeError("Retry loop exited unexpectedly")

    async def robots(self, url: str) -> float:
        """Honor exclusions and crawl-delay, caching rules throughout the batch."""
        parts = urlsplit(url)
        origin = urlunsplit((parts.scheme, parts.netloc, "", "", ""))
        if origin not in self._robots:
            response = await self._request(
                origin + "/robots.txt",
                {"User-Agent": self.settings.USER_AGENT},
                obey_robots=False,
            )
            parser = None
            delay = 0.0
            if response.status_code not in {404, 410}:
                response.raise_for_status()
                parser = RobotFileParser()
                parser.parse(response.text.splitlines())
                delay = float(parser.crawl_delay(self.settings.USER_AGENT) or 0)
            self._robots[origin] = (parser, delay)
        parser, delay = self._robots[origin]
        if parser and not parser.can_fetch(self.settings.USER_AGENT, url):
            raise RobotsDenied("robots.txt disallows collection")
        return delay
