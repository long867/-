"""Import reviewed backfill JSONL in small, idempotent PostgreSQL transactions."""

import argparse
import asyncio
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert

from app.core.cache import invalidate_public_cache
from app.core.db import SessionFactory
from app.models import Article, ArticleChunk, Policy, Source
from pipeline.fetchers.base import timestamp
from pipeline.processors.dedup import normalize_title, normalize_url, simhash
from pipeline.processors.entities import extract_entities
from pipeline.processors.policy_document import general_mineral_policy
from pipeline.processors.translator import (
    number_words,
    numbers,
    numeric_translation_valid,
    summary_measurements_valid,
)
from pipeline.schemas import RawArticle, SourceDefinition

ENRICHED_FIELDS = {
    "title_zh",
    "summary",
    "summary_zh",
    "content_zh",
    "is_translated",
    "minerals",
    "regions",
    "companies",
    "projects",
    "policy_names",
    "tags",
    "category",
    "quality_score",
    "relevance_score",
}


def validate_record(value: dict[str, Any]) -> tuple[SourceDefinition, RawArticle, dict]:
    """Reject empty, unreviewed, mislabeled, or unrelated editorial records."""
    source = SourceDefinition.model_validate(value["source"])
    article = RawArticle.model_validate(value["article"])
    enriched = {
        key: item for key, item in value["enriched"].items() if key in ENRICHED_FIELDS
    }
    if article.source_name != source.name:
        raise ValueError("Article publisher does not match its source")
    if not re.search(r"[\u3400-\u9fff]", enriched.get("title_zh", "")):
        raise ValueError("Reviewed Chinese title required")
    summary = enriched.get("summary_zh", "")
    if not 100 <= len(summary) <= 200 or not re.search(r"[\u3400-\u9fff]", summary):
        raise ValueError("Reviewed Chinese summary required")
    if not enriched.get("minerals") and not general_mineral_policy(
        source, article.title, article.content
    ):
        raise ValueError("At least one grounded mineral is required")
    if any("{{MI_NUM_" in str(item) for item in enriched.values()):
        raise ValueError("Unresolved evidence placeholder")
    if not 0 <= enriched.get("quality_score", -1) <= 100:
        raise ValueError("Invalid quality score")
    if not 0 <= enriched.get("relevance_score", -1) <= 100:
        raise ValueError("Invalid relevance score")
    if enriched.get("category") not in {"news", "price", "policy", "report", "company"}:
        raise ValueError("Invalid category")
    title = enriched["title_zh"]
    evidence = article.title + "\n" + article.content
    if not numeric_translation_valid(article.title, title):
        raise ValueError("Reviewed title changed source numbers")
    if not summary_measurements_valid(article.title, title):
        raise ValueError("Reviewed title changed source units")
    if set(numbers(summary)) - set(numbers(evidence) + number_words(evidence)):
        raise ValueError("Reviewed summary contains unsupported numbers")
    if not summary_measurements_valid(evidence, summary):
        raise ValueError("Reviewed summary changed source units")
    extracted = extract_entities(evidence)
    for field in ("minerals", "regions"):
        if set(enriched.get(field, [])) - set(extracted[field]):
            raise ValueError(f"Reviewed {field} are absent from original evidence")
    return source, article, enriched


async def import_record(value: dict[str, Any], *, publish: bool) -> str:
    """Write a real article and exact original-text evidence spans atomically."""
    raw_value = value.get("article")
    if not isinstance(raw_value, dict) or not isinstance(raw_value.get("url"), str):
        raise ValueError("Original article URL required")
    url = normalize_url(raw_value["url"])
    # Replays cannot change existing records. Avoid repeating expensive editorial
    # validation over an unchanged archive before discovering its URL already exists.
    async with SessionFactory() as existing:
        if await existing.scalar(select(Article.id).where(Article.url == url)):
            return "duplicate"
    definition, raw, enriched = validate_record(value)
    async with SessionFactory.begin() as db:
        await db.execute(text("SELECT pg_advisory_xact_lock(31415926)"))
        source = await db.scalar(select(Source).where(Source.url == definition.url))
        if source is None:
            config = dict(definition.parser_config)
            config.pop("pagination", None)
            config.pop("emit_progress", None)
            config["max_items"] = min(40, int(config.get("max_items", 10)))
            source = Source(
                **definition.model_dump(exclude={"parser_config", "active"}),
                active=False,
                config_json=config,
            )
            db.add(source)
            await db.flush()
        if await db.scalar(select(Article.id).where(Article.url == url)):
            return "duplicate"
        # Exact original fingerprint avoids copies with changed tracking URLs.
        fingerprint = simhash(raw.content)
        if len(raw.content) >= 200 and await db.scalar(
            select(Article.id).where(Article.content_fingerprint == fingerprint)
        ):
            return "duplicate"
        article_id = await db.scalar(
            insert(Article)
            .values(
                source_id=source.id,
                title=raw.title,
                content=raw.content[:100000],
                url=url,
                published_at=raw.published_at,
                language=raw.language,
                raw_json=raw.raw_json
                | {
                    "backfill": True,
                    "editorial_translation": "title_and_summary",
                    "body_translation": "original"
                    if enriched.get("content_zh") is None
                    else "chinese",
                    "collection_source_url": definition.url,
                },
                content_fingerprint=fingerprint,
                title_normalized=normalize_title(raw.title),
                status="published" if publish else "processed",
                **enriched,
            )
            .on_conflict_do_nothing(index_elements=[Article.url])
            .returning(Article.id)
        )
        if article_id is None:
            return "duplicate"
        if enriched["category"] == "policy":
            effective = timestamp(raw.raw_json.get("effective_date"))
            db.add(
                Policy(
                    title=raw.title,
                    title_zh=enriched["title_zh"],
                    url=url,
                    summary_zh=enriched["summary_zh"],
                    minerals=enriched["minerals"],
                    country=raw.raw_json.get("policy_country")
                    or definition.region
                    or "未知",
                    region=definition.region,
                    effective_date=effective.date() if effective else None,
                    impact_score=0,
                )
            )
        original = raw.content[:100000]
        search_header = (
            raw.title
            + "\n"
            + enriched["title_zh"]
            + "\n"
            + enriched["summary_zh"]
            + "\n"
        )
        for index, start in enumerate(range(0, len(original), 600)):
            end = min(start + 700, len(original))
            db.add(
                ArticleChunk(
                    article_id=article_id,
                    chunk_index=index,
                    text=original[start:end],
                    search_text=search_header + original[start:end],
                    start_char=start,
                    end_char=end,
                    embedding=None,
                )
            )
    return "published" if publish else "processed"


async def run(path: Path, *, publish: bool = False) -> dict:
    """Stream records so a small server never loads the entire corpus in memory."""
    counts: Counter = Counter()
    sources: Counter = Counter()
    with path.open(encoding="utf-8") as records:
        for index, line in enumerate(records, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            outcome = await import_record(value, publish=publish)
            counts[outcome] += 1
            if outcome != "duplicate":
                sources[value["source"]["name"]] += 1
            if index % 25 == 0:
                await invalidate_public_cache()
                print(
                    json.dumps(
                        {"imported_records": index, **dict(counts)}, ensure_ascii=False
                    ),
                    flush=True,
                )
    await invalidate_public_cache()
    result = {"outcomes": dict(counts), "new_per_source": dict(sources)}
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return result


def main() -> None:
    """Require an explicit publication flag for reviewed local batch output."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.path, publish=args.publish))


if __name__ == "__main__":
    main()
