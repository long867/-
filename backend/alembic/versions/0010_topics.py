"""Account-owned topic proposals, original evidence and durable bookmarks."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010_topics"
down_revision = "0009_conversation_context"
branch_labels = None
depends_on = None


def identity() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    ]


def upgrade() -> None:
    """Create new tables without altering existing intelligence behavior."""
    op.create_table(
        "topics",
        *identity(),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(20), nullable=False),
        *[
            sa.Column(name, sa.Text(), nullable=False)
            for name in ("title", "title_zh", "summary", "rationale")
        ],
        *[
            sa.Column(
                name,
                postgresql.ARRAY(sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::text[]"),
            )
            for name in ("keywords", "minerals", "regions")
        ],
        sa.Column("heat_score", sa.Float(), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("window", sa.String(10), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_refresh_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "user_id", "fingerprint", name="uq_topics_owner_fingerprint"
        ),
        sa.CheckConstraint(
            "type IN ('achievement','social_science')", name="ck_topics_type"
        ),
        sa.CheckConstraint("heat_score BETWEEN 0 AND 100", name="ck_topics_heat"),
        sa.CheckConstraint("source IN ('generated','manual')", name="ck_topics_source"),
        sa.CheckConstraint("mode IN ('rule','llm')", name="ck_topics_mode"),
        sa.CheckConstraint("window IN ('7d','30d','90d')", name="ck_topics_window"),
    )
    op.create_index(
        "ix_topics_owner_window", "topics", ["user_id", "window", "created_at"]
    )
    op.create_table(
        "topic_evidence",
        *identity(),
        sa.Column(
            "topic_id",
            sa.Uuid(),
            sa.ForeignKey("topics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "article_id",
            sa.Uuid(),
            sa.ForeignKey("articles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_type", sa.String(10), nullable=False),
        sa.Column("quote_field", sa.String(10), nullable=False),
        *[
            sa.Column(name, sa.Text(), nullable=False)
            for name in ("quote", "source_url", "support")
        ],
        *[
            sa.Column(name, sa.Integer(), nullable=False)
            for name in ("position", "start_char", "end_char")
        ],
        sa.UniqueConstraint("topic_id", "position", name="uq_topic_evidence_position"),
        sa.CheckConstraint(
            "evidence_type IN ('article','policy','event')",
            name="ck_topic_evidence_type",
        ),
        sa.CheckConstraint(
            "quote_field IN ('title','content')", name="ck_topic_evidence_field"
        ),
        sa.CheckConstraint(
            "position >= 1 AND start_char >= 0 AND end_char > start_char",
            name="ck_topic_evidence_span",
        ),
    )
    op.create_index("ix_topic_evidence_topic", "topic_evidence", ["topic_id"])
    op.create_table(
        "topic_bookmarks",
        *identity(),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "topic_id",
            sa.Uuid(),
            sa.ForeignKey("topics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "topic_id", name="uq_topic_bookmark"),
    )
    op.create_index("ix_topic_bookmarks_topic_id", "topic_bookmarks", ["topic_id"])


def downgrade() -> None:
    """Drop only this module's tables, in foreign-key order."""
    op.drop_table("topic_bookmarks")
    op.drop_table("topic_evidence")
    op.drop_table("topics")
