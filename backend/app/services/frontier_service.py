"""Read published scholarly records separately from news and decision research."""

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article, Source
from app.schemas.frontier import (
    FrontierDirection,
    FrontierMineral,
    FrontierOverview,
    FrontierPage,
    FrontierPaper,
    FrontierQuery,
)
from app.services.article_service import escape_search, public_conditions
from pipeline.config.research import RESEARCH_DIRECTIONS


def public_papers() -> list[Any]:
    """Never expose pending, hidden, future-dated or unrelated report records."""
    return public_conditions() + [
        Article.category == "report",
        Article.raw_json["document_kind"].astext == "research_paper",
        Source.config_json["adapter"].astext == "crossref_journal",
        Article.published_at <= datetime.now(UTC),
    ]


def paper_out(article: Article, source_name: str) -> FrontierPaper:
    """Whitelist public bibliographic fields; keep collector configuration private."""
    meta = article.raw_json
    has_abstract = meta.get("abstract_available") is True
    return FrontierPaper(
        id=article.id,
        title=article.title,
        title_zh=article.title_zh,
        summary_zh=article.summary_zh,
        doi=meta.get("doi", ""),
        url=article.url,
        source_name=source_name,
        journal=meta.get("journal", ""),
        publisher=meta.get("publisher", ""),
        authors=meta.get("authors", []),
        institutions=meta.get("institutions", []),
        minerals=article.minerals,
        directions=meta.get("research_directions", []),
        published_at=article.published_at,
        published_date=meta.get("published_date"),
        date_precision=meta.get("date_precision", "unknown"),
        abstract_available=has_abstract,
        evidence_scope="abstract" if has_abstract else "bibliographic",
    )


async def overview(db: AsyncSession) -> FrontierOverview:
    """Report actual publication coverage and the last successful collection."""
    rows = (
        await db.execute(
            select(Article.raw_json, Article.minerals, Article.published_at)
            .join(Source)
            .where(*public_papers())
        )
    ).all()
    fields: Counter[str] = Counter()
    minerals: Counter[str] = Counter()
    journals: set[str] = set()
    recent = abstract_count = 0
    cutoff = datetime.now(UTC) - timedelta(days=30)
    for meta, names, stamp in rows:
        fields.update(set(meta.get("research_directions", [])))
        minerals.update(set(names))
        if meta.get("journal"):
            journals.add(meta["journal"])
        abstract_count += meta.get("abstract_available") is True
        recent += stamp >= cutoff
    collected = await db.scalar(
        select(func.max(Source.last_fetched_at)).where(
            Source.config_json["adapter"].astext == "crossref_journal"
        )
    )
    return FrontierOverview(
        total=len(rows),
        recent_30_days=recent,
        abstract_count=abstract_count,
        journal_count=len(journals),
        last_collected_at=collected,
        directions=[
            FrontierDirection(
                key=key, name=names[0], english_name=names[1], count=fields[key]
            )
            for key, names in RESEARCH_DIRECTIONS.items()
        ],
        minerals=[
            FrontierMineral(name=name, count=count)
            for name, count in minerals.most_common(40)
        ],
    )


async def list_papers(db: AsyncSession, query: FrontierQuery) -> FrontierPage:
    """Filter safely and page by publication date with stable tie breaking."""
    filters = public_papers() + [
        Article.published_at >= datetime.now(UTC) - timedelta(days=query.days)
    ]
    if query.direction:
        filters.append(
            Article.raw_json["research_directions"].contains([query.direction])
        )
    if query.mineral:
        filters.append(Article.minerals.contains([query.mineral.strip()]))
    if query.search and query.search.strip():
        filters.append(
            func.concat_ws(
                " ",
                Article.title,
                Article.title_zh,
                Article.summary_zh,
                Article.raw_json["authors"].astext,
                Article.raw_json["institutions"].astext,
                Article.raw_json["journal"].astext,
                Article.raw_json["doi"].astext,
            ).ilike("%" + escape_search(query.search) + "%", escape="\\")
        )
    total = (
        await db.scalar(
            select(func.count()).select_from(Article).join(Source).where(*filters)
        )
        or 0
    )
    rows = (
        await db.execute(
            select(Article, Source.name)
            .join(Source)
            .where(*filters)
            .order_by(Article.published_at.desc(), Article.id)
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        )
    ).all()
    return FrontierPage(
        items=[paper_out(article, name) for article, name in rows],
        total=total,
        page=query.page,
        page_size=query.page_size,
        has_more=query.page * query.page_size < total,
        overview=await overview(db),
    )


async def get_paper(db: AsyncSession, paper_id: UUID) -> FrontierPaper:
    """Return only a published scholarly record, including to anonymous readers."""
    row = (
        await db.execute(
            select(Article, Source.name)
            .join(Source)
            .where(*public_papers(), Article.id == paper_id)
        )
    ).first()
    if row is None:
        raise HTTPException(404, "研究成果不存在或尚未发布")
    return paper_out(*row)
