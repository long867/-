"""Publication-based policy windows with explainable bilingual topic rules."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article, Policy, Source
from app.schemas.intelligence import PolicyUpdate
from app.services.article_service import public_conditions

THEMES = {
    "环保": ("环保", "环境", "environment", "emission", "排放", "保护区"),
    "出口限制": ("出口", "export", "trade restriction", "贸易限制"),
    "税收": ("税", "tax", "royalt", "特许权使用费"),
    "许可与开发": ("permit", "licen", "许可", "开发", "勘探"),
    "供应链": ("supply chain", "供应链", "critical mineral", "关键矿产"),
    "投资与补贴": ("subsid", "investment", "投资", "补贴"),
}


def policy_themes(text: str) -> list[str]:
    """Label text-supported themes without asserting an unsupported legal impact."""
    lowered = text.lower()
    return [
        name for name, words in THEMES.items() if any(word in lowered for word in words)
    ]


async def track_policies(
    db: AsyncSession, start: datetime | None = None, end: datetime | None = None
) -> list[PolicyUpdate]:
    """Include newly published policy, even when its effective date is in the future."""
    end = end or datetime.now(UTC)
    start = start or end - timedelta(days=7)
    rows = (
        await db.execute(
            select(Policy, Article, Source.name)
            .join(Article, Article.url == Policy.url)
            .join(Source, Source.id == Article.source_id)
            .where(
                *public_conditions(),
                Article.published_at >= start,
                Article.published_at < end,
            )
            .order_by(Article.published_at.desc(), Policy.id)
            .limit(100)
        )
    ).all()
    return [
        PolicyUpdate(
            **{
                **PolicyUpdate.model_validate(row).model_dump(),
                "published_at": article.published_at,
                "source_name": name,
                "document_kind": article.raw_json.get("document_kind", "policy"),
                "publication_basis": article.raw_json.get(
                    "publication_basis", "source_publication"
                ),
                "themes": policy_themes(
                    f"{row.title} {row.title_zh or ''} {row.summary_zh or ''}"
                ),
            },
        )
        for row, article, name in rows
    ]
