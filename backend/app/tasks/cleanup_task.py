"""Bounded maintenance confined to our cache namespace and rotated log files."""

import time
from pathlib import Path

from app.core.config import get_settings
from app.core.task_history import INDEX, client
from app.tasks.celery_app import celery_app


def cleanup() -> dict:
    """Trim expired history and obsolete generations; Redis expires live TTLs itself."""
    settings = get_settings()
    connection = client()
    deleted = 0
    try:
        history_removed = connection.zremrangebyscore(
            INDEX, "-inf", time.time() - settings.TASK_HISTORY_DAYS * 86400
        )
        generation = connection.get("miningintel:public:v3:version") or "0"
        for index, key in enumerate(
            connection.scan_iter("miningintel:public:v3:*", count=100)
        ):
            if index >= 10000:
                break
            if key == "miningintel:public:v3:version":
                continue
            if key.split(":")[3] != generation:
                deleted += connection.unlink(key)
    finally:
        connection.close()
    directory = Path(settings.LOG_DIR).resolve()
    removed = 0
    if directory.is_dir():
        for path in directory.glob("miningintel-*.jsonl.*"):
            # Symlinks and active .jsonl files are never removed.
            if (
                path.is_symlink()
                or not path.is_file()
                or path.resolve().parent != directory
            ):
                continue
            if path.stat().st_mtime < time.time() - settings.LOG_RETENTION_DAYS * 86400:
                path.unlink()
                removed += 1
    return {
        "obsolete_cache_keys": deleted,
        "history_removed": history_removed,
        "rotated_logs_removed": removed,
    }


@celery_app.task(
    name="miningintel.cleanup",
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_jitter=True,
    max_retries=3,
)
def cleanup_task() -> dict:
    """Run at 02:00 without clearing queues, locks or authentication data."""
    return cleanup()
