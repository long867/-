"""Anonymous, cached scholarly discovery; generation never runs on public GET."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import TypeAdapter

from app.api.deps import DB
from app.core.cache import cached
from app.schemas.frontier import FrontierPage, FrontierPaper, FrontierQuery
from app.services import frontier_service

router = APIRouter(tags=["frontier research"])


@router.get("/frontier", response_model=FrontierPage)
async def frontier(
    request: Request,
    response: Response,
    db: DB,
    query: Annotated[FrontierQuery, Depends()],
) -> FrontierPage:
    """Read latest research by direction, mineral, keyword and date window."""
    return await cached(
        request,
        response,
        "frontier",
        query.model_dump_json(),
        300,
        TypeAdapter(FrontierPage),
        lambda: frontier_service.list_papers(db, query),
    )


@router.get("/frontier/{paper_id}", response_model=FrontierPaper)
async def detail(paper_id: UUID, db: DB) -> FrontierPaper:
    """Expose dated bibliographic provenance without requiring an account."""
    return await frontier_service.get_paper(db, paper_id)
