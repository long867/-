"""Fifteen-minute recovery scan; each document gets an independently retryable job."""

from app.tasks.celery_app import celery_app
from app.tasks.ingest import recover_pending


@celery_app.task(
    name="miningintel.process_new_articles",
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_jitter=True,
    max_retries=3,
)
def process_new_articles() -> dict:
    """Recover undispatched raw rows, preserving failed translations for review."""
    return {"queued": recover_pending.run()}
