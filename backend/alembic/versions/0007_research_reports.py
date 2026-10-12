"""Persist account-scoped, evidence-backed research reports."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_research_reports"
down_revision = "0006_notification_claims"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add research history without changing any existing report or conversation."""
    op.create_table(
        "research_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("request_json", postgresql.JSONB(), nullable=False),
        sa.Column("result_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_research_user_created", "research_reports", ["user_id", "created_at"]
    )


def downgrade() -> None:
    """Remove only the dedicated research archive."""
    op.drop_index("ix_research_user_created", table_name="research_reports")
    op.drop_table("research_reports")
