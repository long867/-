"""Lightweight Beat entrypoint; workers own the full task implementation registry."""

from app.tasks.celery_app import celery_app

# This entrypoint runs in a dedicated scheduler process, never a worker.
# Celery routes named messages using task_routes without importing their bodies.
celery_app.conf.include = ()
