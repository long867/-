"""Canonical article stream, hotspots, timelines and provenance endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response
from pydantic import BaseModel, TypeAdapter
from sqlalchemy import func, select

from app.api.deps import DB
from app.core.cache import cached
from app.models import Article, Source
from app.schemas.api import ArticleDetail, ArticleOut, ArticlePage
from app.schemas.intelligence import ArticleQuery, TimelineOut, TimelineQuery
from app.services import article_service

router = APIRouter(tags=["articles"])


class FacetCount(BaseModel):
    name: str
    count: int


class ArticleFacets(BaseModel):
    minerals: list[FacetCount]
    regions: list[FacetCount]
    tags: list[FacetCount]


@router.get("/facets", response_model=ArticleFacets)
async def facets(db: DB) -> ArticleFacets:
    """Count filters using published evidence without collector metadata."""
    result: dict[str, list[FacetCount]] = {}
    for name in ("minerals", "regions", "tags"):
        values = (
            select(func.unnest(getattr(Article, name)).label("name"))
            .where(*article_service.public_conditions())
            .subquery()
        )
        rows = (
            await db.execute(
                select(values.c.name, func.count())
                .group_by(values.c.name)
                .order_by(func.count().desc(), values.c.name)
                .limit(50)
            )
        ).all()
        result[name] = [FacetCount(name=name, count=count) for name, count in rows]
    return ArticleFacets(**result)


@router.get("/articles", response_model=ArticlePage)
async def articles(db: DB, query: Annotated[ArticleQuery, Query()]) -> ArticlePage:
    """Filter, sort and paginate reviewed articles with source names."""
    return await article_service.list_articles(db, query)


@router.get("/articles/hot", response_model=list[ArticleOut])
async def hot(request: Request, response: Response, db: DB) -> list[ArticleOut]:
    """Top ten articles published within 48 hours; Redis TTL is 300 seconds."""
    return await cached(
        request,
        response,
        "articles:hot",
        "",
        300,
        TypeAdapter(list[ArticleOut]),
        lambda: article_service.hot_articles(db),
    )


@router.get("/articles/timeline", response_model=TimelineOut)
async def article_timeline(
    db: DB,
    query: Annotated[TimelineQuery, Query()],
) -> TimelineOut:
    return await article_service.timeline(db, query, query.group_by)


@router.get("/articles/{article_id}", response_model=ArticleDetail)
async def article_detail(article_id: UUID, db: DB) -> ArticleDetail:
    return await article_service.get_article(db, article_id)


class PublicSource(BaseModel):
    id: UUID
    name: str
    url: str
    category: str
    language: str
    authority_score: int


@router.get("/sources", response_model=list[PublicSource])
async def sources(db: DB) -> list[PublicSource]:
    """Expose attribution, excluding collector credentials and synthetic seeds."""
    rows = (
        await db.scalars(
            select(Source)
            .where(~Source.url.startswith(article_service.DEMO_PREFIX))
            .order_by(Source.name)
            .limit(5000)
        )
    ).all()
    return [PublicSource.model_validate(row, from_attributes=True) for row in rows]
