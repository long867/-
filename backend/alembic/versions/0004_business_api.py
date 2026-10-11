"""Public intelligence indexes, price provenance and personal API credentials."""

import sqlalchemy as sa
from alembic import op

revision = "0004_business_api"
down_revision = "0003_vector_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Extend existing evidence without deleting or replacing article records."""
    for table, name, columns, options in [
        ("articles", "ix_articles_published_at", ["published_at"], {}),
        ("articles", "ix_articles_quality_score", ["quality_score"], {}),
        (
            "articles",
            "ix_articles_companies",
            ["companies"],
            {"postgresql_using": "gin"},
        ),
        ("events", "ix_events_importance", ["importance_score"], {}),
    ]:
        op.create_index(name, table, columns, **options)
    op.add_column("price_records", sa.Column("product", sa.String(200)))
    op.add_column(
        "price_records",
        sa.Column("price_type", sa.String(20), nullable=False, server_default="spot"),
    )
    op.add_column("price_records", sa.Column("source_url", sa.Text()))
    op.add_column(
        "subscriptions",
        sa.Column(
            "email_enabled", sa.Boolean(), nullable=False, server_default="false"
        ),
    )
    op.add_column("reports", sa.Column("evidence_hash", sa.String(64)))
    op.add_column(
        "reports",
        sa.Column("mode", sa.String(20), nullable=False, server_default="extractive"),
    )
    op.create_table(
        "api_keys",
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
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("prefix", sa.String(20), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"])
    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "subscription_id",
            sa.Uuid(),
            sa.ForeignKey("subscriptions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "report_id",
            sa.Uuid(),
            sa.ForeignKey("reports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(100)),
        sa.UniqueConstraint(
            "subscription_id", "report_id", name="uq_notification_report"
        ),
    )


def downgrade() -> None:
    """Remove phase-three additions, leaving original intelligence intact."""
    op.drop_table("notification_deliveries")
    op.drop_table("api_keys")
    for table, names in [
        ("reports", ["mode", "evidence_hash"]),
        ("subscriptions", ["email_enabled"]),
        ("price_records", ["source_url", "price_type", "product"]),
    ]:
        for name in names:
            op.drop_column(table, name)
    for table, name in [
        ("articles", "ix_articles_published_at"),
        ("articles", "ix_articles_quality_score"),
        ("articles", "ix_articles_companies"),
        ("events", "ix_events_importance"),
    ]:
        op.drop_index(name, table_name=table)
