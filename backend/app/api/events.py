"""Public events with importance ordering and associated reviewed articles."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import DB
from app.schemas.api import ArticleOut
from app.schemas.intelligence import EventDetail, EventPage
from app.services.event_service import get_event, list_events

router = APIRouter(tags=["events"])


@router.get("/events", response_model=EventPage)
async def events(
    db: DB,
    mineral: Annotated[str | None, Query(max_length=100)] = None,
    region: Annotated[str | None, Query(max_length=100)] = None,
    importance_score: Annotated[float, Query(ge=0, le=100)] = 0,
    page: Annotated[int, Query(ge=1, le=10000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> EventPage:
    return await list_events(
        db,
        mineral=mineral,
        region=region,
        importance_score=importance_score,
        page=page,
        page_size=page_size,
    )


@router.get("/events/{event_id}", response_model=EventDetail)
async def event_detail(event_id: UUID, db: DB) -> EventDetail:
    return await get_event(db, event_id)


@router.get("/events/{event_id}/articles", response_model=list[ArticleOut])
async def event_articles(event_id: UUID, db: DB) -> list[ArticleOut]:
    return (await get_event(db, event_id)).articles
