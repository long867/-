"""Separate established facts, conditional implications and practical actions."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ResearchInput(BaseModel):
    mineral: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    days: int = Field(default=30, ge=7, le=365)
    role: Literal["general", "procurement", "project", "policy"] = "general"
    focus: str = Field(
        default="矿产资源供需、政策影响与应对措施", min_length=2, max_length=500
    )

    @field_validator("focus", "mineral", "region")
    @classmethod
    def trimmed(cls, value: str | None) -> str | None:
        """Reject padding-only inputs before any database or gateway operation."""
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("请输入有效的主题、矿种或地区")
        return value


class ResearchSource(BaseModel):
    index: int
    article_id: UUID
    title: str
    original_title: str
    original_excerpt: str
    original_hash: str
    snippet: str
    source_name: str
    url: str
    category: str
    document_kind: str = "article"
    published_at: datetime | None
    authority_score: int


class ResearchCoverage(BaseModel):
    article_count: int = 0
    evidence_count: int = 0
    source_count: int = 0
    policy_count: int = 0
    price_observations: int = 0
    latest_published_at: datetime | None = None


class ResearchSnapshot(BaseModel):
    scope: ResearchInput
    coverage: ResearchCoverage
    sources: list[ResearchSource]
    limitations: list[str]
    generated_at: datetime


class ResearchFact(BaseModel):
    text: str = Field(min_length=2, max_length=600)
    source_id: int = Field(ge=1)
    quote: str = Field(min_length=8, max_length=1200)
    quote_field: Literal["title", "content"] = "content"
    start_char: int = 0
    end_char: int = 0


class ResearchScenario(BaseModel):
    title: str = Field(min_length=2, max_length=100)
    direction: Literal["risk", "opportunity", "mixed"]
    impact: str = Field(min_length=10, max_length=600)
    mechanism: str = Field(min_length=10, max_length=600)
    conditions: list[str] = Field(min_length=1, max_length=5)
    source_ids: list[int] = Field(min_length=1, max_length=9)
    confidence: Literal["low", "medium"] = "low"


class ResearchAction(BaseModel):
    title: str = Field(min_length=2, max_length=100)
    detail: str = Field(min_length=10, max_length=600)
    owner: str = Field(min_length=2, max_length=50)
    priority: Literal["high", "medium", "low"] = "medium"
    source_ids: list[int] = Field(min_length=1, max_length=9)


class ResearchGeneration(BaseModel):
    facts: list[ResearchFact] = Field(min_length=1, max_length=6)
    scenarios: list[ResearchScenario] = Field(min_length=1, max_length=4)
    actions: list[ResearchAction] = Field(min_length=1, max_length=6)
    watchlist: list[str] = Field(default_factory=list, max_length=6)


class ResearchOut(ResearchSnapshot):
    id: UUID | None = None
    mode: Literal["llm", "evidence_based", "insufficient"]
    facts: list[ResearchFact] = Field(default_factory=list)
    scenarios: list[ResearchScenario] = Field(default_factory=list)
    actions: list[ResearchAction] = Field(default_factory=list)
    watchlist: list[str] = Field(default_factory=list)
