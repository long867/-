"""Batch country monitoring over published evidence; zero coverage stays explicit."""

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article, Policy, Source
from app.schemas.countries import CountryIntelligence, CountryItem, CountryMonitor
from app.schemas.intelligence import ArticleQuery
from app.services.article_service import (
    article_out,
    country_topic_condition,
    list_articles,
    public_conditions,
)
from pipeline.analyzers.country_topics import TOPIC_LABELS, CountryTopic
from pipeline.config.countries import country_catalog


async def monitor_countries(
    db: AsyncSession,
    *,
    days: int = 7,
    mineral: str | None = None,
    topic: CountryTopic | None = None,
    name: str | None = None,
) -> CountryMonitor:
    """Aggregate all countries in bounded SQL queries instead of per-country reads."""
    now = datetime.now(UTC)
    cutoff, previous = now - timedelta(days=days), now - timedelta(days=days * 2)
    filters = public_conditions() + [
        Article.category != "price",
        (Article.published_at <= now) | Article.published_at.is_(None),
    ]
    if mineral:
        filters.append(Article.minerals.contains([mineral]))
    if topic:
        filters.append(country_topic_condition(topic))
    if name:
        filters.append(Article.regions.contains([name]))
    flattened = (
        select(
            func.unnest(Article.regions).label("name"),
            Article.id,
            Article.published_at,
            Article.source_id,
            *(country_topic_condition(key).label(key) for key in TOPIC_LABELS),
        )
        .where(*filters)
        .subquery()
    )
    recent = [flattened.c.published_at >= cutoff, flattened.c.published_at <= now]
    aggregates = (
        (
            await db.execute(
                select(
                    flattened.c.name,
                    func.count().label("article_count"),
                    func.count().filter(*recent).label("recent_count"),
                    func.count()
                    .filter(
                        flattened.c.published_at >= previous,
                        flattened.c.published_at < cutoff,
                    )
                    .label("previous_count"),
                    func.count(func.distinct(flattened.c.source_id)).label(
                        "source_count"
                    ),
                    func.max(flattened.c.published_at).label("last_published_at"),
                    *(
                        func.count()
                        .filter(*recent, getattr(flattened.c, key))
                        .label(key)
                        for key in TOPIC_LABELS
                    ),
                ).group_by(flattened.c.name)
            )
        )
        .mappings()
        .all()
    )
    counts = {row["name"]: row for row in aggregates}
    ranked = select(
        flattened.c.name,
        flattened.c.id,
        func.row_number()
        .over(
            partition_by=flattened.c.name,
            order_by=(flattened.c.published_at.desc().nullslast(), flattened.c.id),
        )
        .label("rank"),
    ).subquery()
    latest = (
        await db.execute(
            select(ranked.c.name, Article, Source.name)
            .select_from(ranked)
            .join(Article, Article.id == ranked.c.id)
            .join(Source, Source.id == Article.source_id)
            .where(ranked.c.rank == 1)
        )
    ).all()
    articles = {
        region: article_out(article, source) for region, article, source in latest
    }
    # Policy counts include only actual published policy records, never keyword hits.
    policy_rows = (
        await db.execute(
            select(Policy.country, func.count(func.distinct(Policy.id)))
            .join(Article, Article.url == Policy.url)
            .where(*filters)
            .group_by(Policy.country)
        )
    ).all()
    policies = dict(policy_rows)
    items = []
    for meta in country_catalog():
        if name and meta["name"] != name:
            continue
        row = counts.get(meta["name"], {})
        current, prior = row.get("recent_count", 0), row.get("previous_count", 0)
        count = row.get("article_count", 0)
        items.append(
            CountryItem(
                **meta,
                article_count=count,
                recent_count=current,
                previous_count=prior,
                trend="up"
                if current > prior
                else "down"
                if current < prior
                else "flat",
                coverage_status="recent"
                if current
                else "historical"
                if count
                else "uncovered",
                source_count=row.get("source_count", 0),
                policy_count=policies.get(meta["name"], 0),
                last_published_at=row.get("last_published_at"),
                topics={key: row.get(key, 0) for key in TOPIC_LABELS},
                latest_article=articles.get(meta["name"]),
            )
        )
    items.sort(key=lambda item: (-item.recent_count, -item.article_count, item.iso2))
    active, checked = (
        await db.execute(
            select(func.count(), func.max(Source.last_fetched_at)).where(
                Source.active.is_(True), Source.category != "price"
            )
        )
    ).one()
    return CountryMonitor(
        items=items,
        total=len(items),
        covered=sum(bool(i.article_count) for i in items),
        recent=sum(bool(i.recent_count) for i in items),
        window_days=days,
        topic_labels=TOPIC_LABELS,
        generated_at=now,
        last_successful_fetch_at=checked,
        active_sources=active,
    )


async def country_intelligence(db: AsyncSession, name: str) -> CountryIntelligence:
    """Return a country's profile and recent sourced reports; unknown names are 404."""
    if name not in {row["name"] for row in country_catalog()}:
        raise HTTPException(404, "国家或地区不在监控目录中")
    monitor = await monitor_countries(db, name=name)
    articles = await list_articles(
        db, ArticleQuery(region=name, page_size=6, exclude_prices=True)
    )
    return CountryIntelligence(
        country=monitor.items[0],
        window_days=7,
        topic_labels=TOPIC_LABELS,
        articles=articles.items,
        generated_at=monitor.generated_at,
    )
