"""Initial MiningIntel schema, frozen independently of ORM metadata.

Revision ID: 0001_initial
"""

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Install vector/search extensions and create all domain tables."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table(
        "events",
        sa.Column("title_zh", sa.Text(), nullable=False),
        sa.Column("summary_zh", sa.Text(), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("article_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "minerals",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "regions",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("importance_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.VECTOR(dim=1024), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("article_count >= 0", name="ck_events_count"),
        sa.CheckConstraint(
            "importance_score BETWEEN 0 AND 100", name="ck_events_importance"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_events_embedding",
        "events",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_events_minerals",
        "events",
        ["minerals"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "ix_events_regions", "events", ["regions"], unique=False, postgresql_using="gin"
    )
    op.create_index("ix_events_updated", "events", ["last_updated_at"], unique=False)
    op.create_table(
        "policies",
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("title_zh", sa.Text(), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=False),
        sa.Column("region", sa.String(length=100), nullable=True),
        sa.Column(
            "minerals",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("summary_zh", sa.Text(), nullable=True),
        sa.Column("impact_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("impact_score BETWEEN 0 AND 100", name="ck_policies_impact"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url"),
    )
    op.create_index(op.f("ix_policies_country"), "policies", ["country"], unique=False)
    op.create_table(
        "price_records",
        sa.Column("mineral", sa.String(length=100), nullable=False),
        sa.Column("price", sa.Numeric(precision=20, scale=6), nullable=False),
        sa.Column("unit", sa.String(length=50), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("change_pct", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("price >= 0", name="ck_prices_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "mineral", "unit", "currency", "date", "source", name="uq_price_observation"
        ),
    )
    op.create_index(
        "ix_prices_mineral_date", "price_records", ["mineral", "date"], unique=False
    )
    op.create_table(
        "reports",
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "sources_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "kind", "period_start", "period_end", name="uq_report_period"
        ),
    )
    op.create_table(
        "sources",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("region", sa.String(length=100), nullable=True),
        sa.Column(
            "language", sa.String(length=20), server_default="en", nullable=False
        ),
        sa.Column("authority_score", sa.Integer(), server_default="5", nullable=False),
        sa.Column("fetch_interval", sa.Integer(), server_default="900", nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("etag", sa.Text(), nullable=True),
        sa.Column("last_modified", sa.Text(), nullable=True),
        sa.Column(
            "config_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "category IN ('news','price','policy','report','company')",
            name="ck_sources_category",
        ),
        sa.CheckConstraint("type IN ('rss','web','api')", name="ck_sources_type"),
        sa.CheckConstraint(
            "authority_score BETWEEN 1 AND 10", name="ck_sources_authority"
        ),
        sa.CheckConstraint("fetch_interval >= 60", name="ck_sources_interval"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url"),
    )
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_admin", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "articles",
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("title_zh", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("summary_zh", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_zh", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("language", sa.String(length=20), nullable=False),
        sa.Column(
            "is_translated", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column("quality_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("relevance_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=True),
        sa.Column("embedding", pgvector.sqlalchemy.VECTOR(dim=1024), nullable=True),
        sa.Column(
            "minerals",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "regions",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "companies",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "projects",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "status", sa.String(length=20), server_default="pending", nullable=False
        ),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','processed','published')", name="ck_articles_status"
        ),
        sa.CheckConstraint(
            "quality_score BETWEEN 0 AND 100", name="ck_articles_quality"
        ),
        sa.CheckConstraint(
            "relevance_score BETWEEN 0 AND 100", name="ck_articles_relevance"
        ),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url"),
    )
    op.create_index(
        "ix_articles_embedding",
        "articles",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index("ix_articles_event", "articles", ["event_id"], unique=False)
    op.create_index(
        "ix_articles_minerals",
        "articles",
        ["minerals"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "ix_articles_regions",
        "articles",
        ["regions"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index("ix_articles_source", "articles", ["source_id"], unique=False)
    op.create_index(
        "ix_articles_status_published",
        "articles",
        ["status", "published_at"],
        unique=False,
    )
    op.create_index(
        "ix_articles_tags", "articles", ["tags"], unique=False, postgresql_using="gin"
    )
    op.create_table(
        "chat_sessions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_chat_sessions_user_id"), "chat_sessions", ["user_id"], unique=False
    )
    op.create_table(
        "pipeline_runs",
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("task_id", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("fetched_count", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_pipeline_runs_task_id"), "pipeline_runs", ["task_id"], unique=False
    )
    op.create_table(
        "subscriptions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "subscribed_minerals",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "subscribed_regions",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "frequency", sa.String(length=20), server_default="daily", nullable=False
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "frequency IN ('daily','weekly')", name="ck_subscriptions_frequency"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_table(
        "article_chunks",
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("search_text", sa.Text(), nullable=False),
        sa.Column("start_char", sa.Integer(), nullable=False),
        sa.Column("end_char", sa.Integer(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.VECTOR(dim=1024), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "start_char >= 0 AND end_char > start_char", name="ck_chunks_span"
        ),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "article_id", "chunk_index", name="uq_chunks_article_index"
        ),
    )
    op.create_index(
        op.f("ix_article_chunks_article_id"),
        "article_chunks",
        ["article_id"],
        unique=False,
    )
    op.create_index(
        "ix_chunks_embedding",
        "article_chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_chunks_search",
        "article_chunks",
        ["search_text"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"search_text": "gin_trgm_ops"},
    )
    op.create_table(
        "chat_messages",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column(
            "sources_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "mode", sa.String(length=30), server_default="extractive", nullable=False
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["chat_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_chat_messages_session_id"),
        "chat_messages",
        ["session_id"],
        unique=False,
    )
    op.execute(
        "CREATE INDEX ix_chunks_fts ON article_chunks "
        "USING gin (to_tsvector('simple', search_text))"
    )


def downgrade() -> None:
    """Drop application tables; leave shared PostgreSQL extensions installed."""
    op.drop_table("chat_messages")
    op.drop_table("article_chunks")
    op.drop_table("subscriptions")
    op.drop_table("pipeline_runs")
    op.drop_table("chat_sessions")
    op.drop_table("articles")
    op.drop_table("users")
    op.drop_table("sources")
    op.drop_table("reports")
    op.drop_table("price_records")
    op.drop_table("policies")
    op.drop_table("events")
