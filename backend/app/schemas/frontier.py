"""Public scholarly metadata with explicit evidence scope and source dates."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Direction = Literal[
    "exploration", "processing", "recycling", "environment", "digital", "governance"
]


class FrontierQuery(BaseModel):
    direction: Direction | None = None
    mineral: str | None = Field(default=None, max_length=100)
    search: str | None = Field(default=None, max_length=200)
    days: int = Field(default=90, ge=1, le=730)
    page: int = Field(default=1, ge=1, le=10000)
    page_size: int = Field(default=12, ge=1, le=50)


class FrontierPaper(BaseModel):
    id: UUID
    title: str
    title_zh: str | None
    summary_zh: str | None
    doi: str
    url: str
    source_name: str
    journal: str
    publisher: str
    authors: list[str]
    institutions: list[str]
    minerals: list[str]
    directions: list[str]
    published_at: datetime | None
    published_date: str | None
    date_precision: Literal["day", "month", "year", "unknown"]
    abstract_available: bool
    evidence_scope: Literal["abstract", "bibliographic"]


class FrontierDirection(BaseModel):
    key: str
    name: str
    english_name: str
    count: int


class FrontierMineral(BaseModel):
    name: str
    count: int


class FrontierOverview(BaseModel):
    total: int
    recent_30_days: int
    abstract_count: int
    journal_count: int
    directions: list[FrontierDirection]
    minerals: list[FrontierMineral]
    last_collected_at: datetime | None
    refresh_interval_hours: int = 24


class FrontierPage(BaseModel):
    items: list[FrontierPaper]
    total: int
    page: int
    page_size: int
    has_more: bool
    overview: FrontierOverview
