"""Typed external API schemas; embeddings and password hashes stay private."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    computed_field,
    field_validator,
    model_validator,
)

from app.core.config import get_settings


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class UserOut(ORMModel):
    id: UUID
    email: str
    is_admin: bool
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


Category = Literal["news", "price", "policy", "report", "company"]


class SourceInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    url: HttpUrl
    type: Literal["rss", "web", "api"] = "rss"
    category: Category = "news"
    region: str | None = Field(default=None, max_length=100)
    language: str = Field(default="en", max_length=20)
    authority_score: int = Field(default=5, ge=1, le=10)
    fetch_interval: int = Field(
        default_factory=lambda: get_settings().FETCH_INTERVAL, ge=60, le=604800
    )
    active: bool = True
    config_json: dict[str, Any] = Field(default_factory=dict)


class SourceOut(ORMModel):
    id: UUID
    name: str
    url: str
    type: str
    category: str
    region: str | None
    language: str
    authority_score: int
    fetch_interval: int
    active: bool
    last_fetched_at: datetime | None
    etag: str | None
    last_modified: str | None
    config_json: dict[str, Any]


class ArticleOut(ORMModel):
    id: UUID
    source_id: UUID
    source_name: str | None = None
    date_precision: Literal["day", "time"] | None = None
    title: str
    title_zh: str | None
    summary: str | None
    summary_zh: str | None
    url: str
    published_at: datetime | None
    fetched_at: datetime
    category: str
    language: str
    is_translated: bool
    quality_score: float
    relevance_score: float
    event_id: UUID | None
    minerals: list[str]
    regions: list[str]
    companies: list[str]
    projects: list[str]
    tags: list[str]
    status: str


class ArticleDetail(ArticleOut):
    content: str
    content_zh: str | None


class ArticlePage(BaseModel):
    items: list[ArticleOut]
    total: int
    page: int
    page_size: int


class EventOut(ORMModel):
    id: UUID
    title_zh: str
    summary_zh: str | None
    first_seen_at: datetime
    last_updated_at: datetime
    article_count: int
    minerals: list[str]
    regions: list[str]
    importance_score: float


class PriceOut(ORMModel):
    id: UUID
    mineral: str
    price: Decimal
    unit: str
    currency: str
    date: date
    source: str
    change_pct: Decimal | None
    product: str | None = None
    price_type: Literal["spot", "futures", "benchmark"] = "spot"
    source_url: str | None = None


class PriceInput(BaseModel):
    mineral: str = Field(min_length=1, max_length=100)
    price: Decimal = Field(ge=0, max_digits=20, decimal_places=6)
    unit: str = Field(min_length=1, max_length=50)
    currency: str = Field(min_length=3, max_length=10)
    date: date
    source: str = Field(min_length=1)
    product: str | None = Field(default=None, max_length=200)
    price_type: Literal["spot", "futures", "benchmark"] = "spot"
    source_url: HttpUrl | None = None


class PolicyOut(ORMModel):
    id: UUID
    title: str
    title_zh: str | None
    country: str
    region: str | None
    minerals: list[str]
    effective_date: date | None
    url: str
    summary_zh: str | None
    impact_score: float
    published_at: datetime | None = None
    source_name: str = "未知来源"
    document_kind: str = "policy"
    publication_basis: str = "source_publication"
    themes: list[str] = Field(default_factory=list)


class SubscriptionInput(BaseModel):
    subscribed_minerals: list[str] = Field(default_factory=list, max_length=50)
    subscribed_regions: list[str] = Field(default_factory=list, max_length=50)
    frequency: Literal["daily", "weekly"] = "daily"
    email_enabled: bool = False
    price_alerts_enabled: bool = False

    @field_validator("subscribed_minerals", "subscribed_regions")
    @classmethod
    def bounded_names(cls, value: list[str]) -> list[str]:
        """Normalize facets and reject blank or oversized subscription names."""
        if any(not item.strip() or len(item.strip()) > 100 for item in value):
            raise ValueError("Subscription names must contain 1..100 characters")
        return sorted(set(item.strip() for item in value))


class SubscriptionOut(SubscriptionInput, ORMModel):
    id: UUID
    created_at: datetime


class ChatInput(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    session_id: UUID | None = None
    minerals: list[str] = Field(default_factory=list, max_length=20)
    regions: list[str] = Field(default_factory=list, max_length=20)
    category: Literal["news", "price", "policy", "report", "company"] | None = None
    start: datetime | None = None
    end: datetime | None = None

    @model_validator(mode="after")
    def ordered_dates(self) -> "ChatInput":
        """Require explicit timezone and a nonempty half-open time window."""
        for value in (self.start, self.end):
            if value is not None and value.tzinfo is None:
                raise ValueError("Time filters must include a timezone")
        if self.start and self.end and self.start >= self.end:
            raise ValueError("start must be earlier than end")
        if len(self.question.strip()) < 2:
            raise ValueError(
                "Question must contain at least two non-padding characters"
            )
        self.question = self.question.strip()
        return self


class Citation(BaseModel):
    index: int
    article_id: UUID
    chunk_id: UUID
    title: str
    url: str
    quote: str
    start_char: int
    end_char: int
    published_at: datetime | None
    source_name: str = "未知来源"
    quote_zh: str | None = None
    summary_zh: str | None = None

    @computed_field
    @property
    def id(self) -> int:
        """Expose the public source number while retaining legacy index."""
        return self.index

    @computed_field
    @property
    def snippet(self) -> str:
        """Always mirror the validated quotation, including narrowed spans."""
        return self.quote


class ChatOut(BaseModel):
    session_id: UUID
    message_id: UUID
    answer: str
    sources: list[Citation]
    mode: Literal["grounded", "extractive", "insufficient", "identity"]


class ChatMessageOut(ORMModel):
    id: UUID
    session_id: UUID
    question: str
    answer: str
    sources_json: list[dict[str, Any]]
    mode: str
    created_at: datetime


class ChatSessionOut(ORMModel):
    id: UUID
    title: str
    created_at: datetime


class ReviewInput(BaseModel):
    status: Literal["processed", "published"]
    tags: list[str] | None = Field(default=None, max_length=50)


class RunOut(ORMModel):
    id: UUID
    source_id: UUID | None
    task_id: str | None
    status: str
    fetched_count: int
    new_count: int
    duplicate_count: int
    error_count: int
    error: str | None
    created_at: datetime
    finished_at: datetime | None


class ReportOut(ORMModel):
    id: UUID
    kind: str
    period_start: date
    period_end: date
    title: str
    content: str
    sources_json: list[dict[str, Any]]
    created_at: datetime
