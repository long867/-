"""Queued work is idempotent across dispatch, recovery and retry signals."""

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.core import processing_queue
from app.tasks import ingest, lifecycle


def test_dispatch_does_not_publish_an_already_queued_article(monkeypatch):
    claim = Mock(return_value=False)
    publish = Mock()
    monkeypatch.setattr(processing_queue, "claim", claim)
    monkeypatch.setattr(ingest.process_article, "apply_async", publish)
    assert ingest.enqueue_article(str(uuid4())) is None
    publish.assert_not_called()


def test_broker_failure_releases_only_the_dispatch_reservation(monkeypatch):
    release = Mock()
    monkeypatch.setattr(processing_queue, "claim", Mock(return_value=True))
    monkeypatch.setattr(processing_queue, "release", release)
    monkeypatch.setattr(
        ingest.process_article, "apply_async", Mock(side_effect=ConnectionError)
    )
    article_id = str(uuid4())
    with pytest.raises(ConnectionError):
        ingest.enqueue_article(article_id)
    publish_args = ingest.process_article.apply_async.call_args.kwargs
    release.assert_called_once_with(article_id, publish_args["task_id"])


def test_retry_keeps_queue_lease_until_terminal_completion(monkeypatch):
    release = Mock()
    monkeypatch.setattr(processing_queue, "release", release)
    monkeypatch.setattr(lifecycle, "record", Mock())
    sender = SimpleNamespace(
        name="miningintel.process_article", request=SimpleNamespace()
    )
    task_id, article_id = str(uuid4()), str(uuid4())
    lifecycle.completed(
        sender=sender, task_id=task_id, state="RETRY", args=[article_id]
    )
    release.assert_not_called()
    lifecycle.completed(
        sender=sender, task_id=task_id, state="SUCCESS", args=[article_id]
    )
    release.assert_called_once_with(article_id, task_id)


def test_recovery_skips_existing_leases_and_bounds_new_dispatches(monkeypatch):
    ids = [str(uuid4()) for _ in range(250)]

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def scalars(self, _statement):
            return SimpleNamespace(all=lambda: ids)

    already_queued = set(ids[:75])
    enqueue = Mock(
        side_effect=lambda value: None if value in already_queued else object()
    )
    monkeypatch.setattr(ingest, "SessionFactory", Session)
    monkeypatch.setattr(ingest, "enqueue_article", enqueue)
    assert ingest.recover_pending.run() == 100
    assert enqueue.call_count == 175


@pytest.mark.integration
def test_atomic_queue_lease_owner_expiry_running_guard_and_terminal_recovery():
    """Real Redis arbitrates concurrent producers without deleting newer leases."""
    article_id = str(uuid4())
    task_ids = [str(uuid4()) for _ in range(12)]
    client = processing_queue.connection()
    marker = processing_queue.LEASE_PREFIX + article_id
    running = "process:" + article_id
    history_key = "miningintel:tasks:"
    try:
        with ThreadPoolExecutor(max_workers=12) as executor:
            claimed = list(
                executor.map(
                    lambda task_id: processing_queue.claim(article_id, task_id),
                    task_ids,
                )
            )
        assert claimed.count(True) == 1
        winner = task_ids[claimed.index(True)]
        assert 0 < client.ttl(marker) <= processing_queue.LEASE_SECONDS
        processing_queue.release(article_id, str(uuid4()))
        assert client.get(marker).decode() == winner

        client.hset(history_key + winner, "state", "RETRY")
        assert not processing_queue.claim(article_id, str(uuid4()))
        client.hset(history_key + winner, "state", "FAILURE")
        replacement = str(uuid4())
        assert processing_queue.claim(article_id, replacement)
        processing_queue.release(article_id, winner)
        assert client.get(marker).decode() == replacement
        processing_queue.release(article_id, replacement)

        client.set(running, "running-fixture", ex=60)
        assert not processing_queue.claim(article_id, str(uuid4()))
        client.delete(running)
        client.set(marker, "abandoned-fixture", ex=60)
        client.expire(marker, 0)
        assert processing_queue.claim(article_id, str(uuid4()))
    finally:
        client.delete(marker, running, *(history_key + task_id for task_id in task_ids))
        client.close()
