"""Authenticated message center with account-scoped read states."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.api.deps import DB, CurrentUser
from app.schemas.intelligence import NoticePage
from app.services.notification_service import list_notices, mark_read

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=NoticePage)
async def notifications(
    db: DB,
    user: CurrentUser,
    response: Response,
    page: Annotated[int, Query(ge=1, le=10000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
) -> NoticePage:
    """Read private user state without caching it in browsers or shared proxies."""
    response.headers["Cache-Control"] = "no-store"
    return await list_notices(db, user, page, page_size)


@router.post("/read-all", status_code=204)
async def read_all(db: DB, user: CurrentUser) -> None:
    await mark_read(db, user)


@router.post("/{notice_id}/read", status_code=204)
async def read_one(notice_id: UUID, db: DB, user: CurrentUser) -> None:
    await mark_read(db, user, notice_id)
