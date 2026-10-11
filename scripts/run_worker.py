"""Run the project's Celery worker, including the verified local PGlite adapter."""

import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

from app.core.config import get_settings


def main() -> None:
    """Use the solo pool on Windows; production Linux workers keep prefork."""
    root = Path(__file__).resolve().parents[1]
    os.environ.setdefault(
        "PROMETHEUS_MULTIPROC_DIR", str(root / "artifacts/celery-metrics")
    )
    args = sys.argv[1:] or ["--loglevel=INFO", "--queues=celery,nlp,insights"]
    if os.name == "nt" and not any(arg.startswith("--pool") for arg in args):
        args += ["--pool=solo"]
        if not any(arg.startswith("--concurrency") for arg in args):
            args += ["--concurrency=1"]
    parsed = urlsplit(get_settings().DATABASE_URL)
    if parsed.hostname == "127.0.0.1" and parsed.port == 55432:
        from scripts.pglite_runner import main as local_runner

        sys.argv = ["run_worker", "--module", "pipeline.worker", *args]
        local_runner()
    else:
        from pipeline.worker import main as native_worker

        sys.argv = ["pipeline.worker", *args]
        native_worker()


if __name__ == "__main__":
    main()
