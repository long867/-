"""Developer helper: freeze explicit initial operations from current metadata."""

from pathlib import Path

from alembic.autogenerate.api import AutogenContext
from alembic.autogenerate.render import render_op_text
from alembic.migration import MigrationContext
from alembic.operations import ops
from app.models import Base


def main() -> None:
    """Write an immutable Alembic revision with explicit tables and indexes."""
    context = AutogenContext(
        MigrationContext.configure(dialect_name="postgresql"),
        opts={
            "sqlalchemy_module_prefix": "sa.",
            "alembic_module_prefix": "op.",
            "user_module_prefix": "pgvector.sqlalchemy.",
        },
    )
    upgrade = [
        "op.execute('CREATE EXTENSION IF NOT EXISTS vector')",
        "op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')",
    ]
    tables = list(Base.metadata.sorted_tables)
    for table in tables:
        upgrade.append(render_op_text(context, ops.CreateTableOp.from_table(table)))
        for index in sorted(table.indexes, key=lambda item: item.name):
            upgrade.append(render_op_text(context, ops.CreateIndexOp.from_index(index)))
    downgrade = [f"op.drop_table({table.name!r})" for table in reversed(tables)]
    source = '''"""Initial MiningIntel schema, frozen independently of ORM metadata.

Revision ID: 0001_initial
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import pgvector.sqlalchemy

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Install vector/search extensions and create all domain tables."""
'''
    source += "\n".join(
        "    " + line for operation in upgrade for line in operation.splitlines()
    )
    source += (
        "\n\n\ndef downgrade() -> None:\n"
        '    """Drop tables; preserve shared database extensions."""\n'
    )
    source += "\n".join("    " + line for line in downgrade) + "\n"
    target = (
        Path(__file__).parents[1]
        / "backend"
        / "alembic"
        / "versions"
        / "0001_initial.py"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise RuntimeError(
            "Initial migration already exists; add a new revision instead"
        )
    target.write_text(source, encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
