"""Mineral facets, timelines, comparable price series and policy pages."""

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.api.deps import DB
from app.schemas.api import PriceOut
from app.schemas.intelligence import ArticleQuery, FacetOut, PolicyPage, TimelineOut
from app.services.article_service import timeline
from app.services.trend_service import facets, list_policies, mineral_prices
from pipeline.processors.entities import lexicon

router = APIRouter(tags=["minerals"])


@router.get("/minerals", response_model=list[FacetOut])
async def minerals(db: DB) -> list[FacetOut]:
    """Return standard minerals with actual counts, including zero-count entries."""
    items = await facets(db, "minerals")
    names = {item.name for item in items}
    items.extend(
        FacetOut(
            name=name, article_count=0, recent_count=0, previous_count=0, trend="flat"
        )
        for name in sorted(set(lexicon()["minerals"]) - names)
    )
    return items


@router.get("/minerals/{name}/timeline", response_model=TimelineOut)
async def mineral_timeline(
    name: str,
    db: DB,
    group_by: Literal["day", "week"] = "day",
    date_from: date | None = None,
    date_to: date | None = None,
) -> TimelineOut:
    return await timeline(
        db, ArticleQuery(mineral=name, date_from=date_from, date_to=date_to), group_by
    )


@router.get("/minerals/{name}/prices", response_model=list[PriceOut])
async def prices(
    name: str,
    db: DB,
    date_from: date | None = None,
    date_to: date | None = None,
    source: Annotated[str | None, Query(max_length=2000)] = None,
    price_type: Literal["spot", "futures", "benchmark"] | None = None,
    limit: Annotated[int, Query(ge=1, le=3650)] = 365,
) -> list[PriceOut]:
    return await mineral_prices(db, name, date_from, date_to, source, price_type, limit)


@router.get("/minerals/{name}/policies", response_model=PolicyPage)
async def policies(
    name: str,
    db: DB,
    region: Annotated[str | None, Query(max_length=100)] = None,
    page: Annotated[int, Query(ge=1, le=10000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PolicyPage:
    return await list_policies(
        db, mineral=name, region=region, page=page, page_size=page_size
    )


@router.get("/prices", response_model=list[PriceOut])
async def all_prices(
    db: DB,
    mineral: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=3650)] = 365,
) -> list[PriceOut]:
    return await mineral_prices(db, mineral, limit=limit)
