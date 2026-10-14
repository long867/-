"""Web dispatch stays lightweight and preserves the queue lease contract."""

import os
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.core import processing_queue, task_dispatch


def test_web_dispatch_does_not_import_worker_collection_modules():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import app.core.task_dispatch; "
                "assert 'app.tasks.ingest' not in sys.modules; "
                "assert 'pipeline.fetchers.collect' not in sys.modules; "
                "assert 'trafilatura' not in sys.modules"
            ),
        ],
        capture_output=True,
        timeout=15,
        env=dict(os.environ, LOG_FILE=""),
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")


def test_named_source_and_article_dispatch_preserve_worker_identifiers(monkeypatch):
    send = Mock(return_value=SimpleNamespace(id="queued"))
    monkeypatch.setattr(task_dispatch.celery_app, "send_task", send)
    identity = str(uuid4())
    task_dispatch.enqueue_source(identity)
    send.assert_called_once_with("miningintel.fetch_source", args=[identity])
    send.reset_mock()
    monkeypatch.setattr(processing_queue, "claim", Mock(return_value=True))
    task_dispatch.enqueue_article(identity)
    assert send.call_args.args == ("miningintel.process_article",)
    assert send.call_args.kwargs["args"] == [identity]
    assert send.call_args.kwargs["task_id"]


def test_lightweight_dispatch_releases_reservation_on_broker_failure(monkeypatch):
    monkeypatch.setattr(processing_queue, "claim", Mock(return_value=True))
    release = Mock()
    monkeypatch.setattr(processing_queue, "release", release)
    send = Mock(side_effect=ConnectionError)
    monkeypatch.setattr(task_dispatch.celery_app, "send_task", send)
    identity = str(uuid4())
    with pytest.raises(ConnectionError):
        task_dispatch.enqueue_article(identity)
    release.assert_called_once_with(identity, send.call_args.kwargs["task_id"])
