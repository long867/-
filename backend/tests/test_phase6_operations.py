"""Real Redis transitions and PostgreSQL administration/security contracts."""

import json
import logging
import os
from uuid import uuid4

import pytest
from app.core import task_history
from app.core.logging import JsonFormatter
from app.models import Article
from app.tasks.celery_app import celery_app
from app.tasks.cleanup_task import cleanup
from app.tasks.scheduler import LeaderScheduler
from test_business_api import business as business


def test_schedule_cadence_and_retry_contract():
    """Required cadence replaces older recovery scans rather than duplicating them."""
    schedules = celery_app.conf.beat_schedule
    expected = {
        "dispatch-due-sources": 1800,
        "recover-pending-articles": 900,
        "hourly-incremental-index": 3600,
        "reconcile-events": 7200,
        "full-trends": 21600,
    }
    for name, interval in expected.items():
        assert schedules[name]["schedule"] == interval
    assert schedules["daily-cleanup"]["schedule"].hour == {2}
    assert celery_app.conf.timezone == "Asia/Shanghai"
    celery_app.loader.import_default_modules()
    for name in (
        "fetch_active_sources",
        "process_new_articles",
        "dispatch_index",
        "cluster_events",
        "analyze_trends",
        "generate_report",
        "cleanup",
    ):
        task = celery_app.tasks["miningintel." + name]
        assert task.max_retries == 3 and task.retry_backoff


def test_metric_router_prefixes_preserve_low_cardinality():
    from app.main import metric_route

    assert (
        metric_route("/api/articles/secret-id", "/articles/{article_id}")
        == "/api/articles/{article_id}"
    )
    assert (
        metric_route("/api/open/articles/secret-id", "/articles/{article_id}")
        == "/api/open/articles/{article_id}"
    )
    assert metric_route("/api/chat/stream", "/stream") == "/api/chat/stream"
    assert metric_route("/api/v1/chat", "") == "/api/v1/chat"
    assert (
        metric_route("/api/v1/admin/tasks", "/api/v1/admin/tasks")
        == "/api/v1/admin/tasks"
    )


def test_logs_redact_secrets_and_exception_values():
    """Both ordinary logs and structured fields are valid safe JSON."""
    record = logging.LogRecord(
        "ops",
        logging.ERROR,
        __file__,
        1,
        '{"event":"failed","api_key":"private-test-key",'
        '"url":"postgresql://user:password@host/db",'
        '"authorization":"Bearer sensitive"}',
        (),
        None,
    )
    output = JsonFormatter().format(record)
    assert "private-test-key" not in output and "password@" not in output
    assert "Bearer sensitive" not in output
    assert json.loads(output)["event"] == "failed"
    try:
        raise RuntimeError("exception-secret-value")
    except RuntimeError:
        import sys

        record.exc_info = sys.exc_info()
        output = JsonFormatter().format(record)
    assert "exception-secret-value" not in output
    assert json.loads(output)["error_type"] == "RuntimeError"
    assert (
        json.loads(output)["stack"][-1]["function"]
        == "test_logs_redact_secrets_and_exception_values"
    )


@pytest.mark.integration
def test_redis_history_prevents_late_producer_regression_and_hides_payloads():
    task_id = str(uuid4())
    connection = task_history.client()
    try:
        task_history.record(task_id, "miningintel.cleanup", "STARTED", retries=0)
        task_history.record(
            task_id,
            "miningintel.cleanup",
            "FAILURE",
            error_type="RuntimeError",
            args="private-api-key",
            result="private-result",
            traceback="private-stack",
        )
        task_history.record(task_id, "miningintel.cleanup", "QUEUED")
        row = task_history.snapshot(task_id)
        assert row["state"] == "FAILURE" and row["error_type"] == "RuntimeError"
        assert not {"args", "result", "traceback"} & row.keys()
        assert connection.ttl(task_history.PREFIX + task_id) > 0
        assert any(
            value["task_id"] == task_id
            for value in task_history.history(1, 100, "FAILURE")["items"]
        )
        assert task_history.snapshot(str(uuid4())) is None
    finally:
        connection.delete(task_history.PREFIX + task_id)
        connection.zrem(task_history.INDEX, task_id)
        connection.close()


@pytest.mark.integration
def test_single_beat_lease_and_cleanup_scope(tmp_path, monkeypatch):
    """Another Beat cannot dispatch; cleanup preserves active logs and foreign keys."""
    from app.core.config import Settings
    from app.tasks import cleanup_task, scheduler
    from celery import Celery

    settings = Settings(LOG_DIR=str(tmp_path), LOG_RETENTION_DAYS=1)
    monkeypatch.setattr(cleanup_task, "get_settings", lambda: settings)
    connection = task_history.client()
    prefix = "miningintel:test:" + uuid4().hex + ":"

    class ScopedRedis:
        def lock(self, key, **kwargs):
            return connection.lock(prefix + key, **kwargs)

        def set(self, key, *args, **kwargs):
            return connection.set(prefix + key, *args, **kwargs)

        def delete(self, *keys):
            return connection.delete(*(prefix + key for key in keys))

        def close(self):
            pass

    monkeypatch.setattr(scheduler, "client", ScopedRedis)
    leader = connection.lock(
        prefix + "miningintel:ops:beat-leader", timeout=90, blocking=False
    )
    assert leader.acquire()
    try:
        with pytest.raises(RuntimeError, match="already running"):
            LeaderScheduler(app=celery_app, schedule_filename=str(tmp_path / "beat"))
    finally:
        leader.release()
    test_app = Celery("phase6-test", broker="memory://")
    test_app.conf.beat_schedule = {"future": {"task": "unused", "schedule": 86400}}
    lazy = LeaderScheduler(app=test_app, lazy=True)
    lazy.close()
    actual = LeaderScheduler(
        app=test_app, schedule_filename=str(tmp_path / "actual-beat")
    )
    try:
        assert 0 <= actual.tick() <= 30
        assert actual.connection.__class__.__module__.startswith("kombu")
        assert connection.exists(prefix + "miningintel:ops:beat-heartbeat")
    finally:
        actual.close()
    active = tmp_path / "miningintel-1.jsonl"
    old = tmp_path / "miningintel-1.jsonl.2020-01-01"
    foreign = tmp_path / "another-app.log"
    for path in (active, old, foreign):
        path.write_text("safe fixture", encoding="utf-8")
        os.utime(path, (100, 100))
    connection.set(prefix + "foreign-cache", "keep")
    try:
        result = cleanup()
        assert result["rotated_logs_removed"] == 1
        assert active.exists() and foreign.exists() and not old.exists()
        assert connection.get(prefix + "foreign-cache") == "keep"
    finally:
        connection.delete(prefix + "foreign-cache")
        connection.close()


@pytest.mark.integration
async def test_admin_security_atomic_batch_and_reprocessing_recovery(
    business, monkeypatch
):
    client = business["client"]
    headers = business["headers"]
    for route in (
        "/api/v1/admin/tasks",
        "/api/v1/admin/system",
        "/api/v1/admin/schedule",
    ):
        assert (await client.get(route)).status_code == 401
        assert (
            await client.get(route, headers=business["other_headers"])
        ).status_code == 403
        response = await client.get(route, headers=headers)
        assert response.status_code == 200, response.text
        assert response.headers["Cache-Control"] == "private, no-store"
    ids = [str(value) for value in business["ids"]]
    result = await client.post(
        "/api/v1/admin/articles/batch",
        headers=headers,
        json={"article_ids": [ids[0], ids[3]], "action": "publish"},
    )
    assert result.status_code == 409
    result = await client.post(
        "/api/v1/admin/articles/batch",
        headers=headers,
        json={"article_ids": [ids[0], str(uuid4())], "action": "hide"},
    )
    assert result.status_code == 404
    async with business["factory"]() as db:
        assert (await db.get(Article, business["ids"][0])).status == "published"
    response = await client.post(
        "/api/v1/admin/articles/batch",
        headers=headers,
        json={"article_ids": [ids[0], ids[0]], "action": "hide"},
    )
    assert response.status_code == 200 and response.json()["changed"] == 1
    from app.tasks.ingest import process_article

    def unavailable(*args):
        raise ConnectionError("broker unavailable")

    monkeypatch.setattr(process_article, "delay", unavailable)
    response = await client.post(
        "/api/v1/admin/articles/batch",
        headers=headers,
        json={"article_ids": [ids[0]], "action": "reprocess"},
    )
    assert response.status_code == 200 and response.json()["dispatch_deferred"]
    async with business["factory"]() as db:
        row = await db.get(Article, business["ids"][0])
        assert row.status == "pending" and row.processing_error is None
