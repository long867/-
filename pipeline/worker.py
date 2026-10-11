"""Celery entrypoint with real multiprocess Prometheus aggregation."""

import os
import sys
from pathlib import Path


def main() -> None:
    """Reset only this worker's metrics directory before importing instrumented code."""
    directory = Path(os.getenv("PROMETHEUS_MULTIPROC_DIR", "/tmp/miningintel-metrics"))
    directory.mkdir(parents=True, exist_ok=True)
    for prefix in ("counter_", "histogram_", "gauge_"):
        for path in directory.glob(prefix + "*.db"):
            if path.is_file() and not path.is_symlink():
                path.unlink()
    os.environ["PROMETHEUS_MULTIPROC_DIR"] = str(directory)
    from app.tasks.celery_app import celery_app
    from prometheus_client import CollectorRegistry, multiprocess, start_http_server

    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry)
    start_http_server(9101, registry=registry)
    celery_app.worker_main(["worker", *sys.argv[1:]])


if __name__ == "__main__":
    main()
