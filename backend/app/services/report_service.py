"""Report archives rechecked against current publication visibility."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Report
from app.schemas.intelligence import DigestOut, ReportPage
from app.services.digest_service import Kind, get_digest
from pipeline.reporters.common import report_bounds


async def get_report(db: AsyncSession, report_id: UUID) -> DigestOut:
    """Restore report periods while discarding prose whose evidence was withdrawn."""
    row = await db.get(Report, report_id)
    if row is None or not row.scheduled:
        raise HTTPException(404, "归档报告不存在")
    result = await get_digest(
        db, row.kind, report_bounds(row.period_start, row.period_end)
    )
    result.id, result.scheduled = row.id, True
    return result


async def list_reports(
    db: AsyncSession, kind: Kind | None, page: int, page_size: int
) -> ReportPage:
    """Page completed reports by their exclusive period end with stable ties."""
    conditions = [Report.scheduled.is_(True)]
    if kind:
        conditions.append(Report.kind == kind)
    total = (
        await db.scalar(select(func.count()).select_from(Report).where(*conditions))
        or 0
    )
    ids = (
        await db.scalars(
            select(Report.id)
            .where(*conditions)
            .order_by(Report.period_end.desc(), Report.created_at.desc(), Report.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return ReportPage(
        items=[await get_report(db, item) for item in ids],
        total=total,
        page=page,
        page_size=page_size,
    )
