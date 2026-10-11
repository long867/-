"""Track semantic index versions and durable Qdrant synchronization."""

import sqlalchemy as sa
from alembic import op

revision = "0003_vector_index"
down_revision = "0002_collection"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add index checkpoints without replacing existing article evidence."""
    op.add_column(
        "articles",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column("articles", sa.Column("indexed_at", sa.DateTime(timezone=True)))
    op.add_column("articles", sa.Column("embedding_model", sa.String(200)))
    op.add_column("articles", sa.Column("embedding_hash", sa.String(64)))
    op.create_table(
        "vector_sync_jobs",
        sa.Column("article_id", sa.Uuid(), primary_key=True),
        sa.Column("revision", sa.String(64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "next_retry_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_error", sa.Text()),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_vector_sync_jobs_next_retry_at", "vector_sync_jobs", ["next_retry_at"]
    )


def downgrade() -> None:
    """Remove only the new checkpoints; preserve original vectors and chunks."""
    op.drop_table("vector_sync_jobs")
    for name in ("embedding_hash", "embedding_model", "indexed_at", "updated_at"):
        op.drop_column("articles", name)
