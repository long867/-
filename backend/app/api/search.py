"""Global search over public articles, events and policies."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.api.deps import DB
from app.schemas.intelligence import ArticleQuery, SearchOut
from app.services.article_service import list_articles
from app.services.event_service import list_events
from app.services.trend_service import list_policies

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchOut)
async def search(
    db: DB,
    q: Annotated[str, Query(min_length=1, max_length=200)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    page: Annotated[int, Query(ge=1, le=10000)] = 1,
    mineral: Annotated[str | None, Query(max_length=100)] = None,
    region: Annotated[str | None, Query(max_length=100)] = None,
    category: Literal["news", "price", "policy", "report", "company"] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> SearchOut:
    """Search safely and respect publication gates for all result types."""
    articles = await list_articles(
        db,
        ArticleQuery(
            search=q,
            page_size=limit,
            page=page,
            mineral=mineral,
            region=region,
            category=category,
            date_from=date_from,
            date_to=date_to,
        ),
    )
    events = await list_events(
        db,
        search=q,
        page_size=limit,
        page=page,
        mineral=mineral,
        region=region,
        date_from=date_from,
        date_to=date_to,
    )
    policies = await list_policies(
        db,
        search=q,
        page_size=limit,
        page=page,
        mineral=mineral,
        region=region,
        date_from=date_from,
        date_to=date_to,
    )
    return SearchOut(
        query=q,
        articles=articles.items,
        events=events.items,
        policies=policies.items,
        counts={
            "articles": articles.total,
            "events": events.total,
            "policies": policies.total,
        },
    )
