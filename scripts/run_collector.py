"""Run ingestion with the project configuration and optional local DB adapter."""

import sys
from urllib.parse import urlsplit

from app.core.config import get_settings


def main() -> None:
    """Keep read-only previews independent of database availability."""
    parsed = urlsplit(get_settings().DATABASE_URL)
    if (
        parsed.hostname == "127.0.0.1"
        and parsed.port == 55432
        and not {"--dry-run", "--list-sources"}.intersection(sys.argv)
    ):
        from scripts.pglite_runner import main as run_pglite

        sys.argv = ["pglite_runner", "--module", "pipeline.run_pipeline", *sys.argv[1:]]
        run_pglite()
    else:
        from pipeline.run_pipeline import main as run_pipeline

        run_pipeline()


if __name__ == "__main__":
    main()
