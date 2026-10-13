"""Separate observation dates from the time a public quotation was collected."""

import sqlalchemy as sa
from alembic import op

revision = "0008_price_freshness"
down_revision = "0007_research_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Retain unknown collection times for legacy observations."""
    op.add_column("price_records", sa.Column("fetched_at", sa.DateTime(timezone=True)))
    op.add_column("price_records", sa.Column("source_name", sa.String(200)))


def downgrade() -> None:
    op.drop_column("price_records", "source_name")
    op.drop_column("price_records", "fetched_at")
