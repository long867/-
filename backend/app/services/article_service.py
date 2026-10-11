"""Parameterized article queries, provenance, publication gates and timelines."""

from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article, Source
from app.schemas.api import ArticleDetail, ArticleOut, ArticlePage
from app.schemas.intelligence import ArticleQuery, TimelineBucket, TimelineOut

DEMO_PREFIX = "https://example.com/miningintel-demo/"


def public_conditions() -> list[Any]:
    """Allow reviewed evidence and exclude the known synthetic seed namespace."""
    return [Article.status == "published", ~Article.url.startswith(DEMO_PREFIX)]


def escape_search(value: str) -> str:
    """Treat LIKE metacharacters literally, while SQLAlchemy binds SQL values."""
    return value.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def date_bounds(
    start: date | datetime | None, end: date | datetime | None
) -> tuple[datetime | None, datetime | None]:
    """Dates include the entire UTC day; timestamp bounds are half-open."""
    lower = (
        datetime.combine(start, time.min, UTC)
        if start and not isinstance(start, datetime)
        else start
    )
    upper = (
        datetime.combine(end + timedelta(days=1), time.min, UTC)
        if end and not isinstance(end, datetime)
        else end
    )
    if lower and upper and lower >= upper:
        raise HTTPException(422, "date_from 必须早于 date_to；日期包含全天")
    return lower, upper


def conditions(query: ArticleQuery) -> list[Any]:
    """Compose safe array, category, literal text and publication-date filters."""
    result = public_conditions()
    for name in ("minerals", "regions", "tags"):
        values = getattr(query, name)
        if values:
            if any(not value.strip() or len(value) > 100 for value in values):
                raise HTTPException(422, "筛选项应包含 1–100 个字符")
            result.append(getattr(Article, name).overlap(values))
    for name in ("mineral", "region", "company", "tag"):
        value = getattr(query, name)
        if value:
            column = getattr(
                Article,
                {
                    "mineral": "minerals",
                    "region": "regions",
                    "company": "companies",
                    "tag": "tags",
                }[name],
            )
            result.append(column.contains([value.strip()]))
    if query.category:
        result.append(Article.category == query.category)
    if query.search and query.search.strip():
        result.append(
            func.concat_ws(
                " ",
                Article.title,
                Article.title_zh,
                Article.summary,
                Article.summary_zh,
            ).ilike("%" + escape_search(query.search) + "%", escape="\\")
        )
    lower, upper = date_bounds(query.date_from, query.date_to)
    if lower:
        result.append(Article.published_at >= lower)
    if upper:
        result.append(Article.published_at < upper)
    return result


def article_out(
    article: Article, source_name: str, *, detail: bool = False
) -> ArticleOut:
    """Attach trusted source metadata without leaking vectors or collector secrets."""
    schema = ArticleDetail if detail else ArticleOut
    return schema.model_validate(article).model_copy(
        update={
            "source_name": source_name,
            "date_precision": "day"
            if (article.raw_json or {}).get("date_precision") == "day"
            else None,
        }
    )


async def list_articles(db: AsyncSession, query: ArticleQuery) -> ArticlePage:
    """Return a stable bounded page; ties are resolved by publication time and ID."""
    filters = conditions(query)
    total = (
        await db.scalar(select(func.count()).select_from(Article).where(*filters)) or 0
    )
    ordering = [Article.published_at.desc().nullslast(), Article.id]
    if query.sort_by == "quality_score":
        ordering.insert(0, Article.quality_score.desc())
    rows = (
        await db.execute(
            select(Article, Source.name)
            .join(Source)
            .where(*filters)
            .order_by(*ordering)
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        )
    ).all()
    return ArticlePage(
        items=[article_out(row, name) for row, name in rows],
        total=total,
        page=query.page,
        page_size=query.page_size,
    )


async def get_article(db: AsyncSession, article_id: UUID) -> ArticleDetail:
    """Never expose pending or withdrawn articles through a detail endpoint."""
    row = (
        await db.execute(
            select(Article, Source.name)
            .join(Source)
            .where(Article.id == article_id, *public_conditions())
        )
    ).first()
    if row is None:
        raise HTTPException(404, "文章不存在")
    return article_out(*row, detail=True)


async def hot_articles(
    db: AsyncSession, now: datetime | None = None
) -> list[ArticleOut]:
    """Rank the last 48 hours by 70% quality and 30% linearly decaying freshness."""
    now = now or datetime.now(UTC)
    freshness = func.greatest(
        0, 1 - func.extract("epoch", now - Article.published_at) / 172800
    )
    rows = (
        await db.execute(
            select(Article, Source.name)
            .join(Source)
            .where(
                *public_conditions(),
                Article.published_at >= now - timedelta(hours=48),
                Article.published_at <= now,
            )
            .order_by((Article.quality_score * 0.7 + freshness * 30).desc(), Article.id)
            .limit(10)
        )
    ).all()
    return [article_out(row, name) for row, name in rows]


async def timeline(
    db: AsyncSession, query: ArticleQuery, group_by: Literal["day", "week"] = "day"
) -> TimelineOut:
    """Aggregate counts in UTC with five representative cards per bucket."""
    bucket = func.date_trunc(group_by, Article.published_at)
    filters = conditions(query) + [Article.published_at.is_not(None)]
    rows = (
        await db.execute(
            select(bucket.label("bucket"), func.count(), func.sum(func.count()).over())
            .where(*filters)
            .group_by(bucket)
            .order_by(bucket.desc())
            .limit(90)
        )
    ).all()
    if not rows:
        return TimelineOut(group_by=group_by, total=0, items=[])
    ranked = (
        select(
            Article.id,
            bucket.label("bucket"),
            func.row_number()
            .over(
                partition_by=bucket, order_by=(Article.published_at.desc(), Article.id)
            )
            .label("rank"),
        )
        .where(*filters)
        .subquery()
    )
    selected = (
        await db.execute(
            select(Article, Source.name, ranked.c.bucket)
            .join(Source)
            .join(ranked, ranked.c.id == Article.id)
            .where(ranked.c.bucket.in_([row[0] for row in rows]), ranked.c.rank <= 5)
            .order_by(ranked.c.bucket.desc(), ranked.c.rank)
        )
    ).all()
    grouped: dict[datetime, list[ArticleOut]] = {}
    for article, source_name, stamp in selected:
        grouped.setdefault(stamp, []).append(article_out(article, source_name))
    items = [
        TimelineBucket(
            date=stamp.date(),
            article_count=count,
            minerals=sorted({m for a in grouped.get(stamp, []) for m in a.minerals}),
            articles=grouped.get(stamp, []),
        )
        for stamp, count, _ in rows
    ]
    total = int(rows[0][2])
    return TimelineOut(group_by=group_by, total=total, items=items)
