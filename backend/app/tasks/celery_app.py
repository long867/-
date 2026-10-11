"""Redis-backed queues and a single timezone-aware Celery Beat scheduler."""

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.tasks import lifecycle  # noqa: F401

settings = get_settings()
configure_logging(settings.LOG_LEVEL)
celery_app = Celery(
    "miningintel",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.ingest",
        "app.tasks.reports",
        "app.tasks.index",
        "app.tasks.business",
        "app.tasks.insights",
        "app.tasks.fetch_task",
        "app.tasks.process_task",
        "app.tasks.cluster_task",
        "app.tasks.trend_task",
        "app.tasks.cleanup_task",
    ],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone=settings.DIGEST_TIMEZONE,
    beat_scheduler="app.tasks.scheduler:LeaderScheduler",
    enable_utc=True,
    task_track_started=True,
    worker_send_task_events=True,
    task_send_sent_event=True,
    worker_hijack_root_logger=False,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    result_expires=86400,
    broker_connection_retry_on_startup=True,
    task_soft_time_limit=540,
    task_time_limit=600,
    broker_transport_options={"visibility_timeout": 3600},
    task_routes={
        "miningintel.process_article": {"queue": "nlp"},
        "miningintel.index_article": {"queue": "nlp"},
        "miningintel.generate_report": {"queue": "insights"},
        "miningintel.refresh_insights": {"queue": "insights"},
        "miningintel.dispatch_notifications": {"queue": "insights"},
        "miningintel.send_notice": {"queue": "insights"},
        "miningintel.cluster_events": {"queue": "insights"},
        "miningintel.analyze_trends": {"queue": "insights"},
        "miningintel.cleanup": {"queue": "insights"},
    },
    beat_schedule={
        **{
            f"current-{kind}-digest": {
                "task": "miningintel.generate_brief",
                "schedule": 900.0,
                "args": [kind],
            }
            for kind in ("daily", "weekly", "monthly")
        },
        "hourly-incremental-index": {
            "task": "miningintel.dispatch_index",
            "schedule": 3600.0,
        },
        "recover-vector-mirror": {
            "task": "miningintel.sync_vectors",
            "schedule": 30.0,
        },
        "dispatch-due-sources": {
            "task": "miningintel.fetch_active_sources",
            "schedule": 1800.0,
        },
        "recover-pending-articles": {
            "task": "miningintel.process_new_articles",
            "schedule": 900.0,
        },
        "reconcile-events": {"task": "miningintel.cluster_events", "schedule": 7200.0},
        "full-trends": {"task": "miningintel.analyze_trends", "schedule": 21600.0},
        "daily-cleanup": {
            "task": "miningintel.cleanup",
            "schedule": crontab(hour=2, minute=0),
        },
        "daily-brief": {
            "task": "miningintel.generate_report",
            "schedule": crontab(hour=8, minute=0),
            "args": ["daily"],
        },
        "weekly-brief": {
            "task": "miningintel.generate_report",
            "schedule": crontab(day_of_week=1, hour=8, minute=0),
            "args": ["weekly"],
        },
        "monthly-brief": {
            "task": "miningintel.generate_report",
            "schedule": crontab(day_of_month=1, hour=8, minute=0),
            "args": ["monthly"],
        },
        "market-insights": {"task": "miningintel.refresh_insights", "schedule": 300.0},
        "recover-notifications": {
            "task": "miningintel.dispatch_notifications",
            "schedule": 60.0,
        },
    },
)
