"""Thirty-minute incremental scan of active sources with source-specific pacing."""

from app.tasks.celery_app import celery_app
from app.tasks.ingest import dispatch_sources, queue_lock


@celery_app.task(
    name="miningintel.fetch_active_sources",
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_jitter=True,
    max_retries=3,
)
def fetch_active_sources() -> dict:
    """Queue due active sources, respecting robots, intervals and cooldowns."""
    lock = queue_lock("miningintel:schedule:fetch")
    if not lock.acquire():
        return {"status": "locked"}
    try:
        return {"queued": dispatch_sources.run()}
    finally:
        lock.release()
