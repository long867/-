"""Account-scoped, source-backed decision research archives."""

from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.entities import Base, Created, Identity


class ResearchReport(Identity, Created, Base):
    __tablename__ = "research_reports"
    __table_args__ = (Index("ix_research_user_created", "user_id", "created_at"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    request_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
