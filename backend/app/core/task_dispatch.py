"""Publish named jobs without importing collectors or NLP into the web process."""

from collections.abc import Callable
from uuid import UUID, uuid4

from celery.result import AsyncResult

from app.core import processing_queue
from app.tasks.celery_app import celery_app


def enqueue_source(source_id: str) -> AsyncResult:
    """Send a validated source identifier; collection is performed by the worker."""
    return celery_app.send_task("miningintel.fetch_source", args=[str(UUID(source_id))])


def enqueue_article(
    article_id: str, *, publisher: Callable[..., AsyncResult] | None = None
) -> AsyncResult | None:
    """Reserve once, publish, and release only this lease on broker failure."""
    article_id = str(UUID(article_id))
    task_id = str(uuid4())
    if not processing_queue.claim(article_id, task_id):
        return None
    try:
        if publisher:
            return publisher(args=[article_id], task_id=task_id)
        return celery_app.send_task(
            "miningintel.process_article", args=[article_id], task_id=task_id
        )
    except Exception:
        processing_queue.release(article_id, task_id)
        raise
