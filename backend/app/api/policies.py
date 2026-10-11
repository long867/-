"""Reviewed policies filtered by mineral, region and explicit effective date."""

from datetime import date as Date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import DB
from app.schemas.api import PolicyOut
from app.schemas.intelligence import PolicyPage
from app.services.trend_service import get_policy, list_policies

router = APIRouter(tags=["policies"])


@router.get("/policies", response_model=PolicyPage)
async def policies(
    db: DB,
    region: Annotated[str | None, Query(max_length=100)] = None,
    mineral: Annotated[str | None, Query(max_length=100)] = None,
    date: Date | None = None,
    date_from: Date | None = None,
    date_to: Date | None = None,
    page: Annotated[int, Query(ge=1, le=10000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PolicyPage:
    """The date parameter denotes policy effective date, not article publication."""
    return await list_policies(
        db,
        region=region,
        mineral=mineral,
        on_date=date,
        page=page,
        page_size=page_size,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/policies/{policy_id}", response_model=PolicyOut)
async def policy_detail(policy_id: UUID, db: DB) -> PolicyOut:
    return await get_policy(db, policy_id)
