"""Start the API using the configured native or local PGlite database."""

import argparse
import os
import sys
from urllib.parse import urlsplit

import uvicorn
from app.core.config import get_settings


def main() -> None:
    """Use PGlite compatibility only for its verified loopback test adapter."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    database_url = get_settings().DATABASE_URL
    parsed = urlsplit(database_url)
    if parsed.hostname == "127.0.0.1" and parsed.port == 55432:
        from scripts.pglite_runner import main as run_pglite

        os.environ["DATABASE_URL"] = database_url
        sys.argv = [
            "pglite_runner",
            "--module",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(args.port),
        ]
        run_pglite()
    else:
        uvicorn.run("app.main:app", host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
