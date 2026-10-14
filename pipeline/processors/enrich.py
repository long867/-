"""Atomic enrichment adapter combining translation, extraction and scoring."""

from datetime import datetime
from typing import Any

from app.core.config import get_settings
from pipeline.processors.extractor import extract, quality_score
from pipeline.processors.translator import translate
from pipeline.schemas import Category, RawArticle, SourceDefinition


async def enrich(
    title: str,
    content: str,
    language: str,
    authority: int,
    *,
    published_at: datetime | None = None,
    category: Category = "news",
    source: SourceDefinition | None = None,
    url: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Preserve original evidence; expose rules-only behavior when LLM is disabled."""
    from pipeline.fetchers.scholarly_fetcher import scholarly_source

    if source is not None and scholarly_source(source):
        from pipeline.processors.academic import enrich_academic

        return await enrich_academic(
            title, content, language, authority, published_at, metadata or {}
        )
    if get_settings().ENRICHMENT_MODE == "editorial":
        from pipeline.processors.backfill import (
            EditorialDocument,
            enrich_editorial_batch,
        )

        if source is None or url is None:
            raise ValueError("Editorial enrichment requires original provenance")
        document = EditorialDocument(
            RawArticle(
                source_name=source.name,
                url=url,
                title=title,
                content=content,
                language=language,
                category=category,
                published_at=published_at,
            ),
            source,
        )
        feedback = None
        for _ in range(2):
            results, feedback = await enrich_editorial_batch([document], feedback)
            if url in results:
                return results[url]
        raise ValueError("Editorial facts did not pass source validation")
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
