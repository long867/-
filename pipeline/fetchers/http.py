"""Bounded public HTTP requests with robots and redirect validation."""

from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx
from app.core.config import get_settings

from pipeline.fetchers.resolver import public_addresses


def canonical_url(url: str) -> str:
    """Remove fragments and known tracking parameters without changing content IDs."""
    parts = urlsplit(url)
    if parts.scheme not in {"https", "http"} or not parts.hostname:
        raise ValueError("Only absolute HTTP(S) URLs are accepted")
    if parts.username or parts.password:
        raise ValueError("URL credentials are forbidden")
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if not key.lower().startswith("utm_")
            and key.lower()
            not in {"fbclid", "gclid", "ref", "referrer", "mc_cid", "mc_eid"}
        ]
    )
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", query, "")
    )


async def validate_public_url(url: str) -> None:
    """Reject local, private, metadata and mixed public/private DNS destinations."""
    parts = urlsplit(canonical_url(url))
    if parts.port not in {None, 80, 443}:
        raise ValueError("Only HTTP(S) standard ports are allowed")
    await public_addresses(parts.hostname)


async def safe_get(url: str, headers: dict[str, str] | None = None) -> httpx.Response:
    """Read at most FETCH_MAX_BYTES, validating every redirect destination."""
    settings = get_settings()
    current = canonical_url(url)
    async with httpx.AsyncClient(
        timeout=settings.FETCH_TIMEOUT, trust_env=False
    ) as client:
        for _ in range(5):
            await validate_public_url(current)
            async with client.stream(
                "GET",
                current,
                headers={"User-Agent": settings.USER_AGENT, **(headers or {})},
            ) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    current = canonical_url(
                        urljoin(current, response.headers["location"])
                    )
                    headers = None  # Do not forward conditional headers across origins.
                    continue
                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > settings.FETCH_MAX_BYTES:
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
                    request=response.request,
                )
    raise ValueError("Too many redirects")


async def check_robots(url: str) -> None:
    """Honor explicit crawler exclusions; fail closed on robots fetch errors."""
    parts = urlsplit(url)
    robots_url = urlunsplit((parts.scheme, parts.netloc, "/robots.txt", "", ""))
    response = await safe_get(robots_url)
    if response.status_code in {404, 410}:
        return
    response.raise_for_status()
    parser = RobotFileParser()
    parser.parse(response.text.splitlines())
    if not parser.can_fetch(get_settings().USER_AGENT, url):
        raise ValueError("robots.txt disallows collection")
