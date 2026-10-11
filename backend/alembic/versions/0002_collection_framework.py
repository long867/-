"""Add durable collector checkpoints, fingerprints and accurate run counters."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_collection"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Extend phase zero tables without rewriting the initial migration."""
    op.add_column(
        "sources",
        sa.Column(
            "fetch_state",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "sources",
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
    )
    for name in ("last_attempted_at", "next_retry_at"):
        op.add_column("sources", sa.Column(name, sa.DateTime(timezone=True)))
    op.add_column("sources", sa.Column("last_error", sa.Text()))
    op.add_column(
        "articles",
        sa.Column(
            "raw_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column("articles", sa.Column("content_fingerprint", sa.String(16)))
    op.add_column("articles", sa.Column("title_normalized", sa.Text()))
    op.add_column(
        "articles",
        sa.Column(
            "policy_names",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
    )
    op.create_index("ix_articles_fingerprint", "articles", ["content_fingerprint"])
    op.create_index(
        "ix_articles_title_normalized",
        "articles",
        ["title_normalized"],
        postgresql_using="gin",
        postgresql_ops={"title_normalized": "gin_trgm_ops"},
    )
    for name in ("new_count", "duplicate_count", "error_count"):
        op.add_column(
            "pipeline_runs",
            sa.Column(name, sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    """Remove only phase one fields and indexes."""
    for name in ("new_count", "duplicate_count", "error_count"):
        op.drop_column("pipeline_runs", name)
    op.drop_index("ix_articles_title_normalized", table_name="articles")
    op.drop_index("ix_articles_fingerprint", table_name="articles")
    for name in ("raw_json", "content_fingerprint", "title_normalized", "policy_names"):
        op.drop_column("articles", name)
    for name in (
        "fetch_state",
        "failure_count",
        "last_attempted_at",
        "next_retry_at",
        "last_error",
    ):
        op.drop_column("sources", name)
