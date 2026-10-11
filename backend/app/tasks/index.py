"""Hourly incremental encoding and independently retryable mirror maintenance."""

import asyncio
from uuid import UUID

from app.core.config import get_settings
from app.rag.indexer import index_article, pending_ids, sync_outbox
from app.tasks.celery_app import celery_app


@celery_app.task(
    name="miningintel.dispatch_index",
    autoretry_for=(Exception,),
    retry_backoff=30,
    retry_jitter=True,
    max_retries=3,
)
def dispatch_index() -> dict:
    """Queue a bounded batch; deferred articles are picked up on the next scan."""
    if not get_settings().ML_ENABLED:
        return {"queued": 0, "mode": "keyword"}
    ids = asyncio.run(pending_ids(get_settings().INDEX_BATCH_SIZE))
    for article_id in ids:
        encode_article.delay(str(article_id))
    return {"queued": len(ids)}


@celery_app.task(
    name="miningintel.index_article",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def encode_article(article_id: str) -> dict:
    """Encode one snapshot, preserving a pending checkpoint on failures."""
    return {
        "article_id": article_id,
        "status": asyncio.run(index_article(UUID(article_id))),
    }


@celery_app.task(
    name="miningintel.sync_vectors",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def sync_vectors() -> dict:
    """Recover Qdrant even when the encoding workers or model are unavailable."""
    return asyncio.run(sync_outbox(get_settings().INDEX_BATCH_SIZE))
