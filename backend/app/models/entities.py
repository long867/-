"""PostgreSQL models with timezone-aware dates and bounded domain scores."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared ORM metadata."""


class Identity:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)


class Created:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


def array_column() -> Any:
    """Create a separate non-null array column with safe defaults."""
    return mapped_column(ARRAY(Text), default=list, server_default=text("'{}'::text[]"))


class Source(Identity, Base):
    __tablename__ = "sources"
    __table_args__ = (
        CheckConstraint("type IN ('rss','web','api')", name="ck_sources_type"),
        CheckConstraint(
            "category IN ('news','price','policy','report','company')",
            name="ck_sources_category",
        ),
        CheckConstraint(
            "authority_score BETWEEN 1 AND 10", name="ck_sources_authority"
        ),
        CheckConstraint("fetch_interval >= 60", name="ck_sources_interval"),
    )
    name: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(Text, unique=True)
    type: Mapped[str] = mapped_column(String(20))
    category: Mapped[str] = mapped_column(String(20))
    region: Mapped[str | None] = mapped_column(String(100))
    language: Mapped[str] = mapped_column(String(20), default="en", server_default="en")
    authority_score: Mapped[int] = mapped_column(default=5, server_default="5")
    fetch_interval: Mapped[int] = mapped_column(default=900, server_default="900")
    active: Mapped[bool] = mapped_column(default=True, server_default="true")
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    etag: Mapped[str | None] = mapped_column(Text)
    last_modified: Mapped[str | None] = mapped_column(Text)
    fetch_state: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    failure_count: Mapped[int] = mapped_column(default=0, server_default="0")
    last_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    config_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )


class Event(Identity, Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint(
            "importance_score BETWEEN 0 AND 100", name="ck_events_importance"
        ),
        CheckConstraint("article_count >= 0", name="ck_events_count"),
        Index("ix_events_updated", "last_updated_at"),
        Index("ix_events_importance", "importance_score"),
        Index("ix_events_minerals", "minerals", postgresql_using="gin"),
        Index("ix_events_regions", "regions", postgresql_using="gin"),
        Index(
            "ix_events_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
    title_zh: Mapped[str] = mapped_column(Text)
    summary_zh: Mapped[str | None] = mapped_column(Text)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    article_count: Mapped[int] = mapped_column(default=0, server_default="0")
    minerals: Mapped[list[str]] = array_column()
    regions: Mapped[list[str]] = array_column()
    importance_score: Mapped[float] = mapped_column(default=0, server_default="0")
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024))


class Article(Identity, Base):
    __tablename__ = "articles"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','processed','published')", name="ck_articles_status"
        ),
        CheckConstraint("quality_score BETWEEN 0 AND 100", name="ck_articles_quality"),
        CheckConstraint(
            "relevance_score BETWEEN 0 AND 100", name="ck_articles_relevance"
        ),
        Index("ix_articles_status_published", "status", "published_at"),
        Index("ix_articles_published_at", "published_at"),
        Index("ix_articles_quality_score", "quality_score"),
        Index("ix_articles_companies", "companies", postgresql_using="gin"),
        Index("ix_articles_source", "source_id"),
        Index("ix_articles_event", "event_id"),
        Index("ix_articles_minerals", "minerals", postgresql_using="gin"),
        Index("ix_articles_regions", "regions", postgresql_using="gin"),
        Index("ix_articles_tags", "tags", postgresql_using="gin"),
        Index("ix_articles_fingerprint", "content_fingerprint"),
        Index(
            "ix_articles_title_normalized",
            "title_normalized",
            postgresql_using="gin",
            postgresql_ops={"title_normalized": "gin_trgm_ops"},
        ),
        Index(
            "ix_articles_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="RESTRICT")
    )
    title: Mapped[str] = mapped_column(Text)
    title_zh: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    summary_zh: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    raw_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    content_fingerprint: Mapped[str | None] = mapped_column(String(16))
    title_normalized: Mapped[str | None] = mapped_column(Text)
    policy_names: Mapped[list[str]] = array_column()
    content_zh: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text, unique=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    category: Mapped[str] = mapped_column(String(20))
    language: Mapped[str] = mapped_column(String(20))
    is_translated: Mapped[bool] = mapped_column(default=False, server_default="false")
    quality_score: Mapped[float] = mapped_column(default=0, server_default="0")
    relevance_score: Mapped[float] = mapped_column(default=0, server_default="0")
    event_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("events.id", ondelete="SET NULL")
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024))
    minerals: Mapped[list[str]] = array_column()
    regions: Mapped[list[str]] = array_column()
    companies: Mapped[list[str]] = array_column()
    projects: Mapped[list[str]] = array_column()
    tags: Mapped[list[str]] = array_column()
    status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending"
    )
    processing_error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    embedding_model: Mapped[str | None] = mapped_column(String(200))
    embedding_hash: Mapped[str | None] = mapped_column(String(64))


class VectorSyncJob(Base):
    """Transactional outbox: Qdrant failures never discard PostgreSQL vectors."""

    __tablename__ = "vector_sync_jobs"
    article_id: Mapped[UUID] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True
    )
    revision: Mapped[str] = mapped_column(String(64))
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    next_retry_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    last_error: Mapped[str | None] = mapped_column(Text)


class ArticleChunk(Identity, Base):
    """Immutable original-text spans used as precise RAG evidence."""

    __tablename__ = "article_chunks"
    __table_args__ = (
        UniqueConstraint("article_id", "chunk_index", name="uq_chunks_article_index"),
        CheckConstraint(
            "start_char >= 0 AND end_char > start_char", name="ck_chunks_span"
        ),
        Index(
            "ix_chunks_search",
            "search_text",
            postgresql_using="gin",
            postgresql_ops={"search_text": "gin_trgm_ops"},
        ),
        Index(
            "ix_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
    article_id: Mapped[UUID] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    search_text: Mapped[str] = mapped_column(Text)
    start_char: Mapped[int] = mapped_column(Integer)
    end_char: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024))


Index(
    "ix_chunks_fts",
    func.to_tsvector(text("'simple'::regconfig"), ArticleChunk.search_text),
    postgresql_using="gin",
)


class PriceRecord(Identity, Base):
    __tablename__ = "price_records"
    __table_args__ = (
        UniqueConstraint(
            "mineral", "unit", "currency", "date", "source", name="uq_price_observation"
        ),
        CheckConstraint("price >= 0", name="ck_prices_positive"),
        Index("ix_prices_mineral_date", "mineral", "date"),
    )
    mineral: Mapped[str] = mapped_column(String(100))
    price: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    unit: Mapped[str] = mapped_column(String(50))
    currency: Mapped[str] = mapped_column(String(10))
    date: Mapped[date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(Text)
    change_pct: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    product: Mapped[str | None] = mapped_column(String(200))
    price_type: Mapped[str] = mapped_column(
        String(20), default="spot", server_default="spot"
    )
    source_url: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_name: Mapped[str | None] = mapped_column(String(200))


class Policy(Identity, Base):
    __tablename__ = "policies"
    __table_args__ = (
        CheckConstraint("impact_score BETWEEN 0 AND 100", name="ck_policies_impact"),
    )
    title: Mapped[str] = mapped_column(Text)
    title_zh: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str] = mapped_column(String(100), index=True)
    region: Mapped[str | None] = mapped_column(String(100))
    minerals: Mapped[list[str]] = array_column()
    effective_date: Mapped[date | None] = mapped_column(Date)
    url: Mapped[str] = mapped_column(Text, unique=True)
    summary_zh: Mapped[str | None] = mapped_column(Text)
    impact_score: Mapped[float] = mapped_column(default=0, server_default="0")


class User(Identity, Created, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    is_admin: Mapped[bool] = mapped_column(default=False, server_default="false")
    active: Mapped[bool] = mapped_column(default=True, server_default="true")


class Subscription(Identity, Created, Base):
    __tablename__ = "subscriptions"
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    subscribed_minerals: Mapped[list[str]] = array_column()
    subscribed_regions: Mapped[list[str]] = array_column()
    frequency: Mapped[str] = mapped_column(
        String(20), default="daily", server_default="daily"
    )
    email_enabled: Mapped[bool] = mapped_column(default=False, server_default="false")
    price_alerts_enabled: Mapped[bool] = mapped_column(
        default=False, server_default="false"
    )
    __table_args__ = (
        CheckConstraint(
            "frequency IN ('daily','weekly')", name="ck_subscriptions_frequency"
        ),
    )


class ChatSession(Identity, Created, Base):
    __tablename__ = "chat_sessions"
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200), default="新咨询")
    context_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )


class ChatMessage(Identity, Created, Base):
    __tablename__ = "chat_messages"
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    sources_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    mode: Mapped[str] = mapped_column(
        String(30), default="extractive", server_default="extractive"
    )


class PipelineRun(Identity, Created, Base):
    __tablename__ = "pipeline_runs"
    source_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL")
    )
    task_id: Mapped[str | None] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(20), default="running")
    fetched_count: Mapped[int] = mapped_column(default=0)
    new_count: Mapped[int] = mapped_column(default=0, server_default="0")
    duplicate_count: Mapped[int] = mapped_column(default=0, server_default="0")
    error_count: Mapped[int] = mapped_column(default=0, server_default="0")
    error: Mapped[str | None] = mapped_column(Text)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Report(Identity, Created, Base):
    __tablename__ = "reports"
    __table_args__ = (
        UniqueConstraint("kind", "period_start", "period_end", name="uq_report_period"),
        Index("ix_reports_scheduled_period", "scheduled", "period_end"),
    )
    kind: Mapped[str] = mapped_column(String(20))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    title: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    sources_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    evidence_hash: Mapped[str | None] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(
        String(20), default="extractive", server_default="extractive"
    )
    data_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    scheduled: Mapped[bool] = mapped_column(default=False, server_default="false")


class Notice(Identity, Created, Base):
    """Public report/price signals with stable deduplication identities."""

    __tablename__ = "notices"
    __table_args__ = (Index("ix_notices_created_at", "created_at"),)
    event_key: Mapped[str] = mapped_column(String(200), unique=True)
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    minerals: Mapped[list[str]] = array_column()
    regions: Mapped[list[str]] = array_column()
    url: Mapped[str] = mapped_column(Text)
    severity: Mapped[str | None] = mapped_column(String(10))
    report_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE")
    )
    price_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("price_records.id", ondelete="CASCADE")
    )


class NoticeRead(Identity, Created, Base):
    """Read state is private to the authenticated user."""

    __tablename__ = "notice_reads"
    __table_args__ = (UniqueConstraint("user_id", "notice_id", name="uq_notice_read"),)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    notice_id: Mapped[UUID] = mapped_column(
        ForeignKey("notices.id", ondelete="CASCADE")
    )


class NoticeDispatch(Identity, Created, Base):
    """Durable channel delivery claims; uncertain outcomes are never silently resent."""

    __tablename__ = "notice_dispatches"
    __table_args__ = (
        UniqueConstraint("notice_id", "recipient", name="uq_notice_dispatch"),
        Index("ix_notice_dispatches_status_created", "status", "created_at"),
    )
    notice_id: Mapped[UUID] = mapped_column(
        ForeignKey("notices.id", ondelete="CASCADE")
    )
    recipient: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(
        String(30), default="pending", server_default="pending"
    )
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(String(100))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class APIKey(Identity, Created, Base):
    """Revocable personal API credentials; only a keyed digest is stored."""

    __tablename__ = "api_keys"
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    prefix: Mapped[str] = mapped_column(String(20))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationDelivery(Identity, Created, Base):
    """One durable email delivery per subscription and report revision."""

    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint("subscription_id", "report_id", name="uq_notification_report"),
    )
    subscription_id: Mapped[UUID] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE")
    )
    report_id: Mapped[UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE")
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(String(100))
