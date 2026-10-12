"""Cached, transparent trend and market anomaly calculations."""

from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request, Response
from pydantic import TypeAdapter

from app.api.deps import DB
from app.core.cache import cached
from app.schemas.intelligence import (
    HotMineral,
    PolicyUpdate,
    PriceAlert,
    PriceTrend,
    TrendOverview,
)
from app.services import trend_service

router = APIRouter(prefix="/trends", tags=["trends"])


@router.get("/overview", response_model=TrendOverview)
async def overview(request: Request, response: Response, db: DB) -> TrendOverview:
    """Provide a dated reading of the actual coverage and market observations."""
    return await cached(
        request,
        response,
        "trends:overview",
        "",
        300,
        TypeAdapter(TrendOverview),
        lambda: trend_service.overview(db),
    )


@router.get("/hot-minerals", response_model=list[HotMineral])
async def hot_minerals(
    request: Request,
    response: Response,
    db: DB,
    window: Annotated[Literal["24h", "48h", "7d"], Query()] = "7d",
) -> list[HotMineral]:
    return await cached(
        request,
        response,
        "trends:hot-minerals",
        window,
        1800,
        TypeAdapter(list[HotMineral]),
        lambda: trend_service.hot_minerals(db, window),
    )


@router.get("/price-alerts", response_model=list[PriceAlert])
async def price_alerts(
    request: Request, response: Response, db: DB
) -> list[PriceAlert]:
    return await cached(
        request,
        response,
        "trends:price-alerts",
        "",
        60,
        TypeAdapter(list[PriceAlert]),
        lambda: trend_service.price_alerts(db),
    )


@router.get("/policy-updates", response_model=list[PolicyUpdate])
async def policy_updates(
    request: Request,
    response: Response,
    db: DB,
    days: Annotated[int, Query(ge=1, le=1460)] = 7,
) -> list[PolicyUpdate]:
    return await cached(
        request,
        response,
        "trends:policy-updates",
        str(days),
        1800,
        TypeAdapter(list[PolicyUpdate]),
        lambda: load_policy_updates(db, days),
    )


async def load_policy_updates(db: DB, days: int) -> list[PolicyUpdate]:
    """Allow explicitly labeled archive windows without calling old policy new."""
    from datetime import UTC, datetime, timedelta

    from pipeline.analyzers.policy_tracker import track_policies

    end = datetime.now(UTC)
    return await track_policies(db, end - timedelta(days=days), end)


@router.get("/price-trends", response_model=list[PriceTrend])
async def price_trends(
    request: Request, response: Response, db: DB
) -> list[PriceTrend]:
    """Expose consecutive quoted movements and real seven-day series."""
    from pipeline.analyzers.price_analyzer import price_analysis

    async def load() -> list[PriceTrend]:
        _, trends = await price_analysis(db)
        return trends

    return await cached(
        request,
        response,
        "trends:price-trends",
        "",
        60,
        TypeAdapter(list[PriceTrend]),
        load,
    )
