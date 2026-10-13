"""Celery signals persist state transitions independently of result expiry."""

import time

import redis
from celery import signals

from app.core import processing_queue
from app.core.task_history import record
from pipeline.metrics import TASK_DURATION, TASKS


@signals.after_task_publish.connect
def published(sender=None, headers=None, routing_key=None, **kwargs) -> None:
    """Record successful broker publication; omit payloads and argument reprs."""
    headers = headers or {}
    record(headers.get("id", ""), sender or "", "QUEUED", queue=routing_key or "celery")


@signals.task_prerun.connect
def started(sender=None, task_id=None, **kwargs) -> None:
    """Bind an attempt start time and worker hostname."""
    sender.request.ops_start = time.monotonic()
    record(
        task_id,
        sender.name,
        "STARTED",
        worker=sender.request.hostname,
        retries=sender.request.retries,
    )


@signals.task_retry.connect
def retrying(sender=None, request=None, reason=None, **kwargs) -> None:
    """Record safe failure type; retried exception messages can contain credentials."""
    cause = getattr(reason, "exc", None)
    record(
        request.id,
        sender.name,
        "RETRY",
        retries=request.retries + 1,
        error_type=type(cause or reason).__name__,
    )


@signals.task_postrun.connect
def completed(sender=None, task_id=None, state=None, args=None, **kwargs) -> None:
    """Track each attempt; preserve the dedicated retry signal's error metadata."""
    duration = max(
        0, time.monotonic() - getattr(sender.request, "ops_start", time.monotonic())
    )
    if sender.name.startswith("miningintel."):
        TASKS.labels(sender.name, state).inc()
        TASK_DURATION.labels(sender.name).observe(duration)
    if state != "RETRY":
        record(task_id, sender.name, state, duration_seconds=round(duration, 3))
    if state in {"SUCCESS", "FAILURE", "REVOKED"}:
        release_processing_lease(sender.name, task_id, args)


def release_processing_lease(name: str, task_id: str, args: list | None) -> None:
    """Keep leases across retries; history/cache outages do not fail a task."""
    if name != "miningintel.process_article" or not args or len(args) != 1:
        return
    try:
        processing_queue.release(str(args[0]), task_id)
    except (redis.RedisError, ValueError):
        import structlog

        structlog.get_logger().warning("processing_lease_release_deferred")


@signals.task_failure.connect
def failed(sender=None, task_id=None, exception=None, **kwargs) -> None:
    """Record final exhaustion without leaking exception text."""
    record(task_id, sender.name, "FAILURE", error_type=type(exception).__name__)


@signals.task_revoked.connect
def revoked(request=None, **kwargs) -> None:
    """Expose cancellations and expired jobs as terminal states."""
    if request:
        record(request.id, request.name, "REVOKED")
        release_processing_lease(request.name, request.id, request.args)


@signals.worker_process_shutdown.connect
def process_shutdown(pid=None, **kwargs) -> None:
    """Remove live gauges for stopped prefork children."""
    from prometheus_client import multiprocess

    if pid:
        multiprocess.mark_process_dead(pid)


@signals.heartbeat_sent.connect
def heartbeat(sender=None, **kwargs) -> None:
    """Publish an expiring liveness marker without a blocking inspect broadcast."""
    import redis

    from app.core.task_history import client

    connection = client()
    try:
        hostname = getattr(getattr(sender, "eventer", None), "hostname", "worker")
        connection.set("miningintel:ops:worker:" + hostname, str(time.time()), ex=90)
    except redis.RedisError:
        pass
    finally:
        connection.close()


@signals.worker_process_init.connect
def child_logging(**kwargs) -> None:
    """Give each prefork process its own safe rotating file handler."""
    from app.core.config import get_settings
    from app.core.logging import configure_logging

    configure_logging(get_settings().LOG_LEVEL)
