"""Source-backed decision research and account-owned archives."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response
from pydantic import TypeAdapter
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.core.cache import cached
from app.models import ResearchReport
from app.schemas.research import ResearchInput, ResearchOut
from app.services.research_service import (
    evidence_based_research,
    generate_research,
    get_research,
    research_snapshot,
)

router = APIRouter(prefix="/api/research", tags=["decision research"])


@router.get("/overview", response_model=ResearchOut)
async def overview(
    request: Request,
    response: Response,
    db: DB,
    mineral: Annotated[str | None, Query(max_length=100)] = None,
    region: Annotated[str | None, Query(max_length=100)] = None,
    days: Annotated[int, Query(ge=7, le=365)] = 30,
) -> ResearchOut:
    """Read actual coverage and dated evidence without invoking a language model."""
    scope = ResearchInput(mineral=mineral, region=region, days=days)

    async def load() -> ResearchOut:
        return evidence_based_research(await research_snapshot(db, scope))

    return await cached(
        request,
        response,
        "research:overview",
        scope.model_dump_json(),
        300,
        TypeAdapter(ResearchOut),
        load,
    )


@router.post("", response_model=ResearchOut)
async def create(
    payload: ResearchInput, response: Response, db: DB, user: CurrentUser
) -> ResearchOut:
    """Generate Chinese facts, conditional implications and practical actions."""
    response.headers["Cache-Control"] = "private, no-store"
    return await generate_research(db, user.id, payload)


@router.get("/history", response_model=list[dict])
async def history(response: Response, db: DB, user: CurrentUser) -> list[dict]:
    """Read only the current account's saved research; never cache it publicly."""
    response.headers["Cache-Control"] = "private, no-store"
    rows = (
        await db.scalars(
            select(ResearchReport)
            .where(ResearchReport.user_id == user.id)
            .order_by(ResearchReport.created_at.desc())
            .limit(20)
        )
    ).all()
    return [
        {
            "id": str(row.id),
            "focus": row.request_json.get("focus", "矿产研判"),
            "created_at": row.created_at,
            "mode": row.result_json.get("mode"),
        }
        for row in rows
    ]


@router.get("/reports/{report_id}", response_model=ResearchOut)
async def report(
    report_id: UUID, response: Response, db: DB, user: CurrentUser
) -> ResearchOut:
    """Revalidate the current account's stored evidence before displaying a report."""
    response.headers["Cache-Control"] = "private, no-store"
    return await get_research(db, user.id, report_id)
