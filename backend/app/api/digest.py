"""Fast cached current-period briefs; model generation runs on Celery workers."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response
from pydantic import TypeAdapter

from app.api.deps import DB
from app.core.cache import cached
from app.schemas.intelligence import DigestOut, ReportPage
from app.services.digest_service import Kind, get_digest, period_bounds

router = APIRouter(prefix="/digest", tags=["digest"])


@router.get("/reports", response_model=ReportPage)
async def archive(
    request: Request,
    response: Response,
    db: DB,
    kind: Kind | None = None,
    page: Annotated[int, Query(ge=1, le=10000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=20)] = 10,
) -> ReportPage:
    """Read completed reports; never trigger model generation during a GET request."""
    from app.services.report_service import list_reports

    return await cached(
        request,
        response,
        "digest:archive",
        f"{kind}:{page}:{page_size}",
        3600,
        TypeAdapter(ReportPage),
        lambda: list_reports(db, kind, page, page_size),
    )


@router.get("/reports/{report_id}", response_model=DigestOut)
async def report(
    report_id: UUID, request: Request, response: Response, db: DB
) -> DigestOut:
    """Retrieve a report with current evidence permissions and original sources."""
    from app.services.report_service import get_report

    return await cached(
        request,
        response,
        "digest:report",
        str(report_id),
        3600,
        TypeAdapter(DigestOut),
        lambda: get_report(db, report_id),
    )


async def brief(
    request: Request,
    response: Response,
    db: DB,
    kind: Kind,
    scope: Literal["current", "previous"] = "current",
) -> DigestOut:
    """Serve cached statistics without waiting for an LLM or unavailable queue."""
    from pipeline.reporters.common import previous_period

    bounds = previous_period(kind) if scope == "previous" else period_bounds(kind)
    start, _ = bounds
    return await cached(
        request,
        response,
        "digest:" + kind + ":" + scope,
        str(start.date()),
        3600,
        TypeAdapter(DigestOut),
        lambda: get_digest(db, kind, bounds),
    )


@router.get("/daily", response_model=DigestOut)
async def daily(
    request: Request,
    response: Response,
    db: DB,
    scope: Literal["current", "previous"] = "current",
) -> DigestOut:
    """Today's brief in the configured calendar timezone; cached for one hour."""
    return await brief(request, response, db, "daily", scope)


@router.get("/weekly", response_model=DigestOut)
async def weekly(
    request: Request,
    response: Response,
    db: DB,
    scope: Literal["current", "previous"] = "current",
) -> DigestOut:
    return await brief(request, response, db, "weekly", scope)


@router.get("/monthly", response_model=DigestOut)
async def monthly(
    request: Request,
    response: Response,
    db: DB,
    scope: Literal["current", "previous"] = "current",
) -> DigestOut:
    return await brief(request, response, db, "monthly", scope)
