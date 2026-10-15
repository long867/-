"""Authenticated topic discovery, refresh and persistent account favorites."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.api.deps import DB, CurrentUser
from app.schemas.topics import TopicOut, TopicPage, TopicRefresh, TopicType, TopicWindow
from app.services.topic_service import (
    bookmark_topic,
    generate_topics,
    get_topic,
    list_topics,
)

router = APIRouter(prefix="/api/v1/topics", tags=["topic recommendations"])


def private(response: Response) -> None:
    """Exclude account-bound proposals and favorites from browser/shared caches."""
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "Authorization"


@router.get("/recommendations", response_model=TopicPage)
async def recommendations(
    response: Response,
    db: DB,
    user: CurrentUser,
    type: TopicType | None = None,
    window: TopicWindow = "30d",
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    bookmarked: bool = False,
) -> TopicPage:
    """Read this account's recommendations, initializing with grounded rules."""
    private(response)
    return await list_topics(db, user.id, window, type, limit, bookmarked)


@router.post("/recommendations/refresh", response_model=TopicPage)
async def refresh(
    payload: TopicRefresh, response: Response, db: DB, user: CurrentUser
) -> TopicPage:
    """Synchronously generate a bounded batch; model failures use rule evidence."""
    private(response)
    await generate_topics(db, user.id, payload.window, payload.type, use_llm=True)
    return await list_topics(
        db, user.id, payload.window, payload.type, initialize=False
    )


@router.get("/{topic_id}", response_model=TopicOut)
async def detail(
    topic_id: UUID, response: Response, db: DB, user: CurrentUser
) -> TopicOut:
    """Include live original spans with entity identifiers and source URLs."""
    private(response)
    return await get_topic(db, user.id, topic_id)


@router.put("/{topic_id}/bookmark", status_code=204)
async def save(topic_id: UUID, response: Response, db: DB, user: CurrentUser) -> None:
    """Save once per account and topic."""
    private(response)
    await bookmark_topic(db, user.id, topic_id, True)


@router.delete("/{topic_id}/bookmark", status_code=204)
async def unsave(topic_id: UUID, response: Response, db: DB, user: CurrentUser) -> None:
    """Remove only this account's saved proposal."""
    private(response)
    await bookmark_topic(db, user.id, topic_id, False)
