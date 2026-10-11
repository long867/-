"""Atomic enrichment adapter combining translation, extraction and scoring."""

from datetime import datetime
from typing import Any

from app.core.config import get_settings

from pipeline.processors.extractor import extract, quality_score
from pipeline.processors.translator import translate
from pipeline.schemas import Category


async def enrich(
    title: str,
    content: str,
    language: str,
    authority: int,
    *,
    published_at: datetime | None = None,
    category: Category = "news",
) -> dict[str, Any]:
    """Preserve original evidence; expose rules-only behavior when LLM is disabled."""
    translated = await translate(title, content, language)
    entities = await extract(title, content, category)
    return translated | {
        "minerals": entities.minerals,
        "regions": entities.regions,
        "companies": entities.companies,
        "projects": entities.projects,
        "policy_names": entities.policies,
        "tags": entities.policies,
        "category": entities.category,
        "quality_score": quality_score(authority, content, published_at),
        # Keep the phase-zero API/DB contract: scores exposed there are 0..100.
        "relevance_score": round(entities.relevance_score * 100, 2),
    }


def llm_available() -> bool:
    """Report capability explicitly instead of treating untranslated text as Chinese."""
    return bool(get_settings().LLM_API_KEY.get_secret_value())
