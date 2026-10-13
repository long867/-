"""Validated contracts for the canonical business API."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, EmailStr, Field

from app.schemas.api import (
    ArticleOut,
    Category,
    EventOut,
    ORMModel,
    PolicyOut,
    PriceOut,
    SubscriptionInput,
    SubscriptionOut,
)
from pipeline.analyzers.country_topics import CountryTopic


class ArticleQuery(BaseModel):
    minerals: list[str] = Field(default_factory=list, max_length=20)
    regions: list[str] = Field(default_factory=list, max_length=20)
    tags: list[str] = Field(default_factory=list, max_length=20)
    mineral: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    category: Category | None = None
    topic: CountryTopic | None = None
    exclude_prices: bool = False
    company: str | None = Field(default=None, max_length=200)
    search: str | None = Field(default=None, max_length=200)
    tag: str | None = Field(default=None, max_length=100)
    date_from: date | AwareDatetime | None = None
    date_to: date | AwareDatetime | None = None
    page: int = Field(default=1, ge=1, le=10000)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_by: Literal["published_at", "quality_score"] = "published_at"


class TimelineBucket(BaseModel):
    date: date
    article_count: int
    minerals: list[str]
    articles: list[ArticleOut]


class TimelineQuery(ArticleQuery):
    group_by: Literal["day", "week"] = "day"


class TimelineOut(BaseModel):
    group_by: Literal["day", "week"]
    total: int
    items: list[TimelineBucket]


class EventDetail(EventOut):
    articles: list[ArticleOut]


class EventPage(BaseModel):
    items: list[EventOut]
    total: int
    page: int
    page_size: int


class PolicyPage(BaseModel):
    items: list[PolicyOut]
    total: int
    page: int
    page_size: int


class FacetOut(BaseModel):
    name: str
    article_count: int
    recent_count: int
    previous_count: int
    trend: Literal["up", "down", "flat"]


class HotMineral(BaseModel):
    mineral: str
    count: int
    previous_count: int
    growth_pct: float | None
    is_new: bool
    window: Literal["24h", "48h", "7d"] = "7d"
    heat_score: float = 0
    is_hot: bool = False
    trend: Literal["up", "down", "flat"] = "flat"
    baseline_mean: float = 0
    baseline_std: float = 0
    baseline_samples: int = 0
    baseline_sufficient: bool = False
    z_score: float | None = None
    sparkline: list[int] = Field(default_factory=list)
    attention_score: float = 0


class PriceAlert(PriceOut):
    previous_price: Decimal | None = None
    previous_date: date | None = None
    severity: Literal["red", "yellow", "green"] = "green"
    direction: Literal["up", "down", "flat"] = "flat"


class PriceTrend(PriceOut):
    direction: Literal["up", "down", "flat"] = "flat"
    consecutive_moves: int = 0
    observations: list[dict[str, str]] = Field(default_factory=list)


class TrendOverview(BaseModel):
    article_count: int
    policy_count: int
    latest_published_at: datetime | None
    generated_at: datetime
    signals: list[str]
    interpretation: str
    watchlist: list[str]


class PolicyUpdate(PolicyOut):
    published_at: datetime | None = None
    themes: list[str] = Field(default_factory=list)


class DigestSource(BaseModel):
    article_id: UUID
    title: str
    url: str
    source_name: str
    published_at: datetime | None
    snippet: str


class DigestStats(BaseModel):
    article_count: int
    source_count: int
    minerals: dict[str, int]
    regions: dict[str, int]
    categories: dict[str, int]


class DigestOut(BaseModel):
    id: UUID | None = None
    kind: Literal["daily", "weekly", "monthly"]
    period_start: date
    period_end: date
    timezone: str
    title: str
    content: str
    mode: Literal["extractive", "llm", "empty"]
    generated_at: datetime
    stats: DigestStats
    sources: list[DigestSource]
    analysis: dict = Field(default_factory=dict)
    scheduled: bool = False
    coverage_hash: str = ""
    latest_published_at: datetime | None = None


class ReportPage(BaseModel):
    items: list[DigestOut]
    total: int
    page: int
    page_size: int


class NoticeOut(ORMModel):
    id: UUID
    kind: Literal["report", "price_alert"]
    title: str
    body: str
    minerals: list[str]
    regions: list[str]
    url: str
    created_at: datetime
    read: bool = False
    severity: Literal["red", "yellow", "green"] | None = None


class NoticePage(BaseModel):
    items: list[NoticeOut]
    total: int
    unread_count: int
    page: int
    page_size: int


class SearchOut(BaseModel):
    query: str
    articles: list[ArticleOut]
    events: list[EventOut]
    policies: list[PolicyOut]
    counts: dict[str, int]


class EmailSubscriptionInput(SubscriptionInput):
    email: EmailStr | None = None


class EmailSubscriptionOut(SubscriptionOut):
    email: str


class APIKeyInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    expires_in_days: int = Field(default=90, ge=1, le=365)


class APIKeyOut(ORMModel):
    id: UUID
    name: str
    prefix: str
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None


class APIKeyCreated(APIKeyOut):
    key: str
