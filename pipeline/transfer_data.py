"""Transfer real public evidence between MiningIntel databases, without user secrets."""

import argparse
import asyncio
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from app.core.db import SessionFactory
from app.models import (
    Article,
    ArticleChunk,
    Event,
    Notice,
    Policy,
    PriceRecord,
    Report,
    Source,
)
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

TABLES = [Source, Event, Article, ArticleChunk, PriceRecord, Policy, Report, Notice]


def json_value(value):
    """Serialize vectors and timestamps without users, sessions or subscriptions."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    if hasattr(value, "tolist"):
        return value.tolist()
    raise TypeError(type(value).__name__)


async def export_snapshot(path: Path) -> dict:
    """Export evidence and provenance in FK order to a private local artifact."""
    payload = {}
    async with SessionFactory() as db:
        for model in TABLES:
            rows = (await db.scalars(select(model))).all()
            payload[model.__tablename__] = [
                {
                    column.name: getattr(row, column.name)
                    for column in model.__table__.columns
                }
                for row in rows
            ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, default=json_value, ensure_ascii=False), encoding="utf-8"
    )
    return {table: len(rows) for table, rows in payload.items()}


async def import_snapshot(path: Path) -> dict:
    """Restore once using IDs, preserving conflicting existing rows."""
    from sqlalchemy import Date, DateTime, Numeric

    payload = json.loads(path.read_text(encoding="utf-8"))
    counts = {}
    async with SessionFactory.begin() as db:
        for model in TABLES:
            count = 0
            for raw in payload.get(model.__tablename__, []):
                values = {
                    column.name: raw[column.name]
                    for column in model.__table__.columns
                    if column.name in raw
                }
                for column in model.__table__.columns:
                    value = values.get(column.name)
                    if value is None:
                        continue
                    if isinstance(column.type, DateTime):
                        values[column.name] = datetime.fromisoformat(value)
                    elif isinstance(column.type, Date):
                        values[column.name] = date.fromisoformat(value)
                    elif isinstance(column.type, Numeric):
                        values[column.name] = Decimal(value)
                    elif column.type.__class__.__name__ in {"Uuid", "UUID"}:
                        values[column.name] = UUID(value)
                result = await db.execute(
                    insert(model).values(**values).on_conflict_do_nothing()
                )
                count += result.rowcount
            counts[model.__tablename__] = count
    from app.core.cache import invalidate_public_cache

    await invalidate_public_cache()
    return counts


def main() -> None:
    """Run with export/import and a file path; protect the generated artifact."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["export", "import"])
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    operation = export_snapshot if args.action == "export" else import_snapshot
    print(json.dumps(asyncio.run(operation(args.path))))


if __name__ == "__main__":
    main()
