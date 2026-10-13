"""Country monitoring separates directory size, observed reporting and freshness."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.api import ArticleOut
from app.schemas.intelligence import FacetOut


class CountryItem(FacetOut):
    iso2: str
    iso3: str
    english_name: str
    continent: str
    subregion: str
    kind: Literal["country_or_area", "organization"]
    coverage_status: Literal["recent", "historical", "uncovered"]
    source_count: int = 0
    policy_count: int = 0
    last_published_at: datetime | None = None
    topics: dict[str, int] = Field(default_factory=dict)
    latest_article: ArticleOut | None = None


class CountryMonitor(BaseModel):
    items: list[CountryItem]
    total: int
    covered: int
    recent: int
    window_days: int
    topic_labels: dict[str, str]
    generated_at: datetime
    last_successful_fetch_at: datetime | None = None
    active_sources: int = 0
    refresh_schedule: str = "每 30 分钟检查采集任务；各信源按自身更新间隔执行"
    coverage_note: str = (
        "目录依据联合国 M49 国家与地区表，欧盟单列，动向统计不含价格快照。"
        "国家标签表示报道提及的地点；"
        "主题数量是观察线索，不能直接视为已生效政策或风险评级。"
    )


class CountryIntelligence(BaseModel):
    country: CountryItem
    window_days: int
    topic_labels: dict[str, str]
    articles: list[ArticleOut]
    generated_at: datetime
