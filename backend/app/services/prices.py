"""Idempotent price observations with unit- and source-consistent changes."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PriceRecord
from app.schemas.api import PriceInput


async def store_price(db: AsyncSession, payload: PriceInput) -> None:
    """Upsert a price and recompute the same-series chronological changes."""
    db.info["public_changed"] = True
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:series))"),
        {
            "series": f"{payload.mineral}|{payload.currency}|"
            f"{payload.unit}|{payload.source}"
        },
    )
    await db.execute(
        insert(PriceRecord)
        .values(
            **(
                payload.model_dump()
                | {
                    "fetched_at": datetime.now(UTC),
                    "source_url": str(payload.source_url)
                    if payload.source_url
                    else None,
                }
            )
        )
        .on_conflict_do_update(
            constraint="uq_price_observation",
            set_={
                "fetched_at": datetime.now(UTC),
                "source_name": payload.source_name,
                "price": payload.price,
                "product": payload.product,
                "price_type": payload.price_type,
                "source_url": str(payload.source_url) if payload.source_url else None,
            },
        )
    )
    series = list(
        (
            await db.scalars(
                select(PriceRecord)
                .where(
                    PriceRecord.mineral == payload.mineral,
                    PriceRecord.unit == payload.unit,
                    PriceRecord.currency == payload.currency,
                    PriceRecord.source == payload.source,
                )
                .order_by(PriceRecord.date)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).all()
    )
    previous: Decimal | None = None
    for item in series:
        item.change_pct = (
            ((item.price - previous) / previous * 100).quantize(Decimal("0.000001"))
            if previous
            else None
        )
        previous = item.price
