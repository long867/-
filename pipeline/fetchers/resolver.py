"""Resolve exclusively public destinations, optionally through a trusted DoH IP."""

import asyncio
import ipaddress
import socket
import time
from urllib.parse import urlsplit

import httpx
from app.core.config import get_settings

_cache: dict[tuple[str, str], tuple[float, list[str]]] = {}


async def public_addresses(host: str) -> list[str]:
    """Validate every resolved address; callers connect directly to the result."""
    key = (get_settings().FETCH_DNS_RESOLVER, host)
    cached = _cache.get(key)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None:
        addresses = [str(address)]
    elif resolver := get_settings().FETCH_DNS_RESOLVER:
        endpoint = urlsplit(resolver)
        # Bootstrap without consulting the possibly intercepted system DNS.
        bootstrap = ipaddress.ip_address(endpoint.hostname or "")
        if (
            endpoint.scheme != "https"
            or not bootstrap.is_global
            or endpoint.port not in {None, 443}
            or endpoint.username
        ):
            raise ValueError(
                "DoH endpoint must use a public HTTPS IP without credentials"
            )
        addresses = []
        async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
            for kind in ("A", "AAAA"):
                async with client.stream(
                    "GET",
                    resolver,
                    params={"name": host, "type": kind},
                    headers={"Accept": "application/dns-json"},
                ) as response:
                    response.raise_for_status()
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > 65536:
                            raise ValueError("DNS response too large")
                    payload = httpx.Response(200, content=bytes(body)).json()
                    if payload.get("Status") != 0:
                        raise ValueError("Public DNS resolution failed")
                    addresses.extend(
                        row["data"]
                        for row in payload.get("Answer", [])
                        if row.get("type") in {1, 28}
                    )
    else:
        records = await asyncio.get_running_loop().getaddrinfo(
            host, 443, type=socket.SOCK_STREAM
        )
        addresses = [row[4][0] for row in records]
    if not addresses or any(
        not ipaddress.ip_address(value).is_global for value in addresses
    ):
        raise ValueError("Fetch destination must resolve exclusively to public IPs")
    # Prefer IPv4 on hosts without an IPv6 route, preserving all-address validation.
    result = sorted(
        set(addresses), key=lambda value: ipaddress.ip_address(value).version
    )
    if len(_cache) >= 128:
        _cache.clear()
    _cache[key] = (time.monotonic() + 30, result)
    return result
