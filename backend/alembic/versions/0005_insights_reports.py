"""Structured archives, account read states and durable channel delivery claims."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_insights_reports"
down_revision = "0004_business_api"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Extend the existing corpus without deleting evidence or subscription consent."""
    op.add_column(
        "subscriptions",
        sa.Column(
            "price_alerts_enabled", sa.Boolean(), nullable=False, server_default="false"
        ),
    )
    op.add_column(
        "reports",
        sa.Column(
            "data_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "reports",
        sa.Column("scheduled", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_table(
        "notices",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("event_key", sa.String(200), nullable=False, unique=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "minerals",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "regions",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(10)),
        sa.Column(
            "report_id", sa.Uuid(), sa.ForeignKey("reports.id", ondelete="CASCADE")
        ),
        sa.Column(
            "price_id", sa.Uuid(), sa.ForeignKey("price_records.id", ondelete="CASCADE")
        ),
    )
    op.create_table(
        "notice_reads",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "notice_id",
            sa.Uuid(),
            sa.ForeignKey("notices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "notice_id", name="uq_notice_read"),
    )
    op.create_index("ix_notice_reads_user_id", "notice_reads", ["user_id"])
    op.create_table(
        "notice_dispatches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "notice_id",
            sa.Uuid(),
            sa.ForeignKey("notices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("recipient", sa.String(200), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(100)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("notice_id", "recipient", name="uq_notice_dispatch"),
    )


def downgrade() -> None:
    """Remove only phase-five metadata; original evidence remains intact."""
    op.drop_table("notice_dispatches")
    op.drop_index("ix_notice_reads_user_id", table_name="notice_reads")
    op.drop_table("notice_reads")
    op.drop_table("notices")
    op.drop_column("reports", "scheduled")
    op.drop_column("reports", "data_json")
    op.drop_column("subscriptions", "price_alerts_enabled")
