"""Optional local WASM PostgreSQL checks when Docker is unavailable.

PGlite's socket adapter does not acknowledge asyncpg's Terminate handshake.
This isolated runner closes client transports explicitly; production code is unchanged.
"""

import argparse
import asyncio
import os
import runpy
from urllib.parse import urlsplit
from uuid import uuid4

import asyncpg


async def check_database(url: str) -> None:
    """Restrict this compatibility workaround to the local PGlite test server."""
    parsed = urlsplit(url.replace("postgresql+asyncpg", "postgresql"))
    if parsed.hostname != "127.0.0.1" or parsed.port != 55432:
        raise ValueError("PGlite runner requires 127.0.0.1:55432")
    connection = await asyncpg.connect(
        url.replace("postgresql+asyncpg", "postgresql"),
        ssl=False,
        statement_cache_size=0,
    )
    try:
        version = await connection.fetchval("SELECT version()")
        if "PGlite" not in version:
            raise ValueError("The compatibility runner is restricted to PGlite")
        print(version)
    finally:
        connection.terminate()


async def close_transport(
    self: asyncpg.Connection, *, timeout: float | None = None
) -> None:
    """Terminate only the confirmed test adapter's client transport."""
    self.terminate()


def main() -> None:
    """Run pytest or a pipeline module against the local test database."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", default="pytest")
    args, rest = parser.parse_known_args()
    from app.core.config import get_settings

    url = os.getenv("TEST_DATABASE_URL") or get_settings().DATABASE_URL
    asyncio.run(check_database(url))
    asyncpg.Connection.close = close_transport
    # The adapter multiplexes clients onto one backend with shared statement names.
    asyncpg.Connection._get_unique_id = lambda self, prefix: (
        f"__miningintel_{prefix}_{uuid4().hex}__"
    )
    if args.module == "pytest":
        import pytest

        raise SystemExit(pytest.main(rest))
    import sys

    sys.argv = [args.module, *rest]
    runpy.run_module(args.module, run_name="__main__")


if __name__ == "__main__":
    main()
