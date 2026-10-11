"""SQL aggregation of publication trends, comparable price series and policies."""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article, Policy, PriceRecord
from app.schemas.api import PolicyOut, PriceOut
from app.schemas.intelligence import (
    FacetOut,
    HotMineral,
    PolicyPage,
    PolicyUpdate,
    PriceAlert,
)
from app.services.article_service import escape_search, public_conditions


async def facets(
    db: AsyncSession, name: str, now: datetime | None = None
) -> list[FacetOut]:
    """Compare the current seven days with the preceding seven using published_at."""
    now = now or datetime.now(UTC)
    flattened = (
        select(
            func.unnest(getattr(Article, name)).label("name"),
            Article.published_at.label("published_at"),
        )
        .where(*public_conditions())
        .subquery()
    )
    recent = func.count().filter(
        flattened.c.published_at >= now - timedelta(days=7),
        flattened.c.published_at <= now,
    )
    previous = func.count().filter(
        flattened.c.published_at >= now - timedelta(days=14),
        flattened.c.published_at < now - timedelta(days=7),
    )
    rows = (
        await db.execute(
            select(flattened.c.name, func.count(), recent, previous)
            .group_by(flattened.c.name)
            .order_by(func.count().desc(), flattened.c.name)
        )
    ).all()
    return [
        FacetOut(
            name=value,
            article_count=count,
            recent_count=current,
            previous_count=prior,
            trend="up" if current > prior else "down" if current < prior else "flat",
        )
        for value, count, current, prior in rows
    ]


async def hot_minerals(db: AsyncSession, window: str = "7d") -> list[HotMineral]:
    """Expose statistically qualified, publication-based coverage signals."""
    from pipeline.analyzers.hot_detector import hot_minerals as detect

    return await detect(db, window)


async def price_alerts(db: AsyncSession) -> list[PriceAlert]:
    """Recalculate genuine daily changes from comparable consecutive quotes."""
    from pipeline.analyzers.price_analyzer import price_analysis

    alerts, _ = await price_analysis(db)
    return alerts


def policy_conditions(
    *,
    mineral: str | None = None,
    region: str | None = None,
    on_date: date | None = None,
    search: str | None = None,
) -> list:
    """Policies are visible only while their supporting article is published."""
    result = public_conditions()
    if mineral:
        result.append(Policy.minerals.contains([mineral]))
    if region:
        result.append(or_(Policy.region == region, Policy.country == region))
    if on_date:
        result.append(Policy.effective_date == on_date)
    if search:
        result.append(
            func.concat_ws(" ", Policy.title, Policy.title_zh, Policy.summary_zh).ilike(
                "%" + escape_search(search) + "%", escape="\\"
            )
        )
    return result


async def list_policies(
    db: AsyncSession,
    *,
    mineral: str | None = None,
    region: str | None = None,
    on_date: date | None = None,
    search: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> PolicyPage:
    """Return a stable policy page with separate publication and effective dates."""
    stmt = (
        select(Policy)
        .join(Article, Article.url == Policy.url)
        .where(
            *policy_conditions(
                mineral=mineral, region=region, on_date=on_date, search=search
            )
        )
    )
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "开始日期不能晚于结束日期")
    if date_from:
        stmt = stmt.where(Policy.effective_date >= date_from)
    if date_to:
        stmt = stmt.where(Policy.effective_date <= date_to)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = (
        await db.scalars(
            stmt.order_by(
                Policy.effective_date.desc().nullslast(),
                Article.published_at.desc().nullslast(),
                Policy.id,
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return PolicyPage(
        items=[PolicyOut.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_policy(db: AsyncSession, policy_id: UUID) -> PolicyOut:
    """Apply the same publication gate to individual policy records."""
    item = await db.scalar(
        select(Policy)
        .join(Article, Article.url == Policy.url)
        .where(Policy.id == policy_id, *public_conditions())
    )
    if item is None:
        raise HTTPException(404, "政策不存在")
    return PolicyOut.model_validate(item)


async def policy_updates(db: AsyncSession) -> list[PolicyUpdate]:
    """Return the past week's newly published policies with supported themes."""
    from pipeline.analyzers.policy_tracker import track_policies

    return await track_policies(db)


async def mineral_prices(
    db: AsyncSession,
    mineral: str | None = None,
    start: date | None = None,
    end: date | None = None,
    source: str | None = None,
    price_type: str | None = None,
    limit: int = 365,
) -> list[PriceOut]:
    """Never blend different products, sources or units into a single price series."""
    if start and end and start > end:
        raise HTTPException(422, "date_from 不能晚于 date_to")
    stmt = select(PriceRecord).where(
        ~PriceRecord.source.startswith("https://example.com/miningintel-demo/")
    )
    if mineral:
        stmt = stmt.where(PriceRecord.mineral == mineral)
    if start:
        stmt = stmt.where(PriceRecord.date >= start)
    if end:
        stmt = stmt.where(PriceRecord.date <= end)
    if source:
        stmt = stmt.where(PriceRecord.source == source)
    if price_type:
        stmt = stmt.where(PriceRecord.price_type == price_type)
    rows = (
        await db.scalars(
            stmt.order_by(
                PriceRecord.date.desc(), PriceRecord.source, PriceRecord.id
            ).limit(limit)
        )
    ).all()
    return [PriceOut.model_validate(row) for row in rows]
