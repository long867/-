"""Typed operations contracts; no task payloads, credentials or user questions."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class TaskRecord(BaseModel):
    task_id: str
    name: str
    state: str
    updated_at: datetime
    queued_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    retries: int = 0
    queue: str | None = None
    worker: str | None = None
    error_type: str | None = None
    duration_seconds: float | None = None


class TaskPage(BaseModel):
    items: list[TaskRecord]
    total: int
    page: int
    page_size: int


class SystemMetrics(BaseModel):
    articles_total: int
    articles_published: int
    articles_today: int
    chat_total: int
    chat_today: int
    requests_5m: int
    errors_5m: int
    error_rate_5m: float
    active_sources: int
    failing_sources: int
    pending_articles: int
    workers: list[str]
    beat_alive: bool
    queues: dict[str, int]


class BatchReview(BaseModel):
    article_ids: list[UUID] = Field(min_length=1, max_length=100)
    action: Literal["publish", "hide", "reprocess"]


class BatchResult(BaseModel):
    changed: int
    queued: int = 0
    task_ids: list[str] = []
    dispatch_deferred: bool = False


class ScheduleOut(BaseModel):
    name: str
    task: str
    schedule: str
    timezone: str
