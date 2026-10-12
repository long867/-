"""SQL aggregation of publication trends, comparable price series and policies."""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article, Policy, PriceRecord, Source
from app.schemas.api import PolicyOut, PriceOut
from app.schemas.intelligence import (
    FacetOut,
    HotMineral,
    PolicyPage,
    PolicyUpdate,
    PriceAlert,
    TrendOverview,
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
    date_basis: str = "effective_date",
) -> PolicyPage:
    """Return a stable policy page with separate publication and effective dates."""
    stmt = (
        select(Policy, Article, Source.name)
        .join(Article, Article.url == Policy.url)
        .join(Source, Source.id == Article.source_id)
        .where(
            *policy_conditions(
                mineral=mineral, region=region, on_date=on_date, search=search
            )
        )
    )
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "开始日期不能晚于结束日期")
    if date_from:
        stmt = stmt.where(
            (
                func.date(Article.published_at)
                if date_basis == "published_at"
                else Policy.effective_date
            )
            >= date_from
        )
    if date_to:
        stmt = stmt.where(
            (
                func.date(Article.published_at)
                if date_basis == "published_at"
                else Policy.effective_date
            )
            <= date_to
        )
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = (
        await db.execute(
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
        items=[policy_view(policy, article, name) for policy, article, name in items],
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_policy(db: AsyncSession, policy_id: UUID) -> PolicyOut:
    """Apply the same publication gate to individual policy records."""
    item = (
        await db.execute(
            select(Policy, Article, Source.name)
            .join(Article, Article.url == Policy.url)
            .join(Source, Source.id == Article.source_id)
            .where(Policy.id == policy_id, *public_conditions())
        )
    ).first()
    if item is None:
        raise HTTPException(404, "政策不存在")
    return policy_view(*item)


def policy_view(policy: Policy, article: Article, source_name: str) -> PolicyOut:
    """Expose publication and document type without inventing effective dates."""
    from pipeline.analyzers.policy_tracker import policy_themes

    return PolicyOut.model_validate(policy).model_copy(
        update={
            "published_at": article.published_at,
            "source_name": source_name,
            "document_kind": article.raw_json.get("document_kind", "policy"),
            "publication_basis": article.raw_json.get(
                "publication_basis", "source_publication"
            ),
            "themes": policy_themes(article.title + " " + (article.summary_zh or "")),
        }
    )


async def policy_updates(db: AsyncSession) -> list[PolicyUpdate]:
    """Return the past week's newly published policies with supported themes."""
    from pipeline.analyzers.policy_tracker import track_policies

    return await track_policies(db)


async def overview(db: AsyncSession) -> TrendOverview:
    """Explain coverage and comparable quotations without forecasting price targets."""
    from pipeline.analyzers.price_analyzer import price_analysis

    now = datetime.now(UTC)
    conditions = public_conditions() + [Article.published_at <= now]
    latest = await db.scalar(select(func.max(Article.published_at)).where(*conditions))
    count = (
        await db.scalar(
            select(func.count())
            .select_from(Article)
            .where(*conditions, Article.published_at >= now - timedelta(days=7))
        )
        or 0
    )
    policy_count = (
        await db.scalar(
            select(func.count())
            .select_from(Policy)
            .join(Article, Article.url == Policy.url)
            .where(*conditions)
        )
        or 0
    )
    hot = await hot_minerals(db, "7d")
    signals = [
        f"近七天收录 {count} 篇已发布资料，政策库包含 {policy_count} 份公开文件。"
    ]
    if hot:
        leader = max(hot, key=lambda row: row.count)
        text = f"{leader.mineral}的报道量为 {leader.count} 篇"
        if leader.growth_pct is not None:
            text += f"，较前一周期变化 {leader.growth_pct:+.1f}%"
        signals.append(text + "；报道量反映关注度，不能直接等同于供需或价格变化。")
        if not any(row.baseline_sufficient for row in hot):
            signals.append("历史统计样本仍在积累，暂不将报道量变化判定为统计异常热点。")
    alerts, series = await price_analysis(db)
    for row in series[:3]:
        change = (
            f"，较上一可比报价变化 {row.change_pct:+.2f}%"
            if row.change_pct is not None
            else ""
        )
        signals.append(
            f"{row.date} 的{row.product or row.mineral}报价为 {row.price} "
            f"{row.currency}/{row.unit}{change}。"
        )
    if not alerts:
        signals.append("已有可比价格记录未触发超过百分之三的单日异动条件。")
    if not series or any(len(row.observations) < 7 for row in series):
        signals.append("连续价格样本不足，暂不能判断长期价格走势。")
    return TrendOverview(
        article_count=count,
        policy_count=policy_count,
        latest_published_at=latest,
        generated_at=now,
        signals=signals,
        interpretation="先核对报道主题、政策执行状态和同口径报价，再判断供应链、项目和采购可能受到的影响。研判页会列出成立条件与应对建议。",
        watchlist=[
            "政策执行细则及后续修订",
            "项目许可、融资与实际投产进度",
            "同产品报价、库存和成交数据",
        ],
    )


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
