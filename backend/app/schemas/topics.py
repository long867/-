"""Bounded topic inputs and traceable account-private recommendations."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

TopicType = Literal["achievement", "social_science"]
TopicWindow = Literal["7d", "30d", "90d"]


class TopicRefresh(BaseModel):
    type: TopicType | None = None
    window: TopicWindow = "30d"


class TopicEvidenceOut(BaseModel):
    id: UUID
    evidence_type: Literal["article", "policy", "event"]
    entity_id: UUID
    article_id: UUID
    quote: str
    quote_field: Literal["title", "content"]
    source_url: str
    support: str
    position: int
    start_char: int
    end_char: int
    title: str
    source_name: str
    published_at: datetime | None


class TopicOut(BaseModel):
    id: UUID
    type: TopicType
    title: str
    title_zh: str
    summary: str
    rationale: str
    keywords: list[str]
    minerals: list[str]
    regions: list[str]
    heat_score: float
    source: Literal["generated", "manual"]
    mode: Literal["rule", "llm"]
    window: TopicWindow
    created_at: datetime
    generated_at: datetime
    bookmarked: bool
    evidence_count: int
    evidence: list[TopicEvidenceOut]
    limitation: str = (
        "推荐为待验证的研究设想；报道关注度不代表市场预测或申报成功率。"
        "尚未系统检索文献，研究空白与创新性依据不足，需自行核查。"
    )


class TopicPage(BaseModel):
    items: list[TopicOut]
    total: int
    window: TopicWindow
    mode: Literal["rule", "llm", "mixed", "insufficient"]
    message: str


class DraftReason(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_index: int = Field(ge=1)
    quote_field: Literal["title", "content"]
    quote: str = Field(min_length=8, max_length=800)
    support: str = Field(min_length=10, max_length=240)


class DraftTopic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=6, max_length=120)
    rationale: list[DraftReason] = Field(min_length=1, max_length=4)


class DraftTopics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topics: list[DraftTopic] = Field(min_length=1, max_length=12)
