"""Batch-query latest comparable series without inventing directory prices."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PriceRecord, Source
from app.schemas.api import PriceOut
from app.schemas.intelligence import FacetOut
from app.schemas.market import MineralMarket, MineralMarketItem
from app.services.trend_service import facets
from pipeline.config.minerals import mineral_catalog


async def market_directory(db: AsyncSession) -> MineralMarket:
    """Fetch one latest observation per series with no per-mineral database queries."""
    counts = {item.name: item for item in await facets(db, "minerals")}
    ranked = (
        select(
            PriceRecord.id,
            func.row_number()
            .over(
                partition_by=(
                    PriceRecord.mineral,
                    PriceRecord.source,
                    PriceRecord.unit,
                    PriceRecord.currency,
                ),
                order_by=(PriceRecord.date.desc(), PriceRecord.id),
            )
            .label("rank"),
        )
        .where(~PriceRecord.source.startswith("https://example.com/miningintel-demo/"))
        .subquery()
    )
    rows = (
        await db.scalars(
            select(PriceRecord)
            .join(ranked, PriceRecord.id == ranked.c.id)
            .where(ranked.c.rank == 1)
            .order_by(PriceRecord.date.desc(), PriceRecord.source)
        )
    ).all()
    prices: dict[str, list[PriceOut]] = {}
    for row in rows:
        prices.setdefault(row.mineral, []).append(PriceOut.model_validate(row))
    catalog = mineral_catalog()
    known = {item["name"] for item in catalog}
    # Preserve imported, explicitly named products outside the maintained directory.
    catalog = catalog + [
        {"name": name, "symbol": "MIN", "english_name": name, "group": "其他资源"}
        for name in sorted((set(counts) | set(prices)) - known)
    ]
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    items = []
    for meta in catalog:
        name = meta["name"]
        observations = prices.get(name, [])
        status = "unavailable"
        if observations:
            status = "stale" if (today - observations[0].date).days > 7 else "available"
        facet = counts.get(
            name,
            FacetOut(
                name=name,
                article_count=0,
                recent_count=0,
                previous_count=0,
                trend="flat",
            ),
        )
        items.append(
            MineralMarketItem(
                **facet.model_dump(),
                **{key: value for key, value in meta.items() if key != "name"},
                prices=observations,
                price_status=status,
            )
        )
    checked = await db.scalar(
        select(func.max(Source.last_fetched_at)).where(
            Source.active.is_(True), Source.category == "price"
        )
    )
    return MineralMarket(
        items=items,
        total=len(items),
        quoted_minerals=sum(bool(item.prices) for item in items),
        quoted_products=len(rows),
        latest_checked_at=checked,
        generated_at=datetime.now(UTC),
    )
