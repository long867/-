"""Notification claim timestamps and archive/dispatch indexes."""

import sqlalchemy as sa
from alembic import op

revision = "0006_notification_claims"
down_revision = "0005_insights_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Recover a lost worker by its claim time, independent of queue age."""
    op.add_column(
        "notice_dispatches", sa.Column("claimed_at", sa.DateTime(timezone=True))
    )
    op.execute(
        "UPDATE notice_dispatches SET claimed_at = created_at WHERE status = 'sending'"
    )
    op.create_index(
        "ix_reports_scheduled_period", "reports", ["scheduled", "period_end"]
    )
    op.create_index("ix_notices_created_at", "notices", ["created_at"])
    op.create_index(
        "ix_notice_dispatches_status_created",
        "notice_dispatches",
        ["status", "created_at"],
    )


def downgrade() -> None:
    """Keep every report and notice when removing these operational improvements."""
    op.drop_index("ix_notice_dispatches_status_created", table_name="notice_dispatches")
    op.drop_index("ix_notices_created_at", table_name="notices")
    op.drop_index("ix_reports_scheduled_period", table_name="reports")
    op.drop_column("notice_dispatches", "claimed_at")
