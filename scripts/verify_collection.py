"""Read-only acceptance counters for a source's persisted collection corpus."""

import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy import func, select

from app.core.db import SessionFactory
from app.models import Article, ArticleChunk, Source


async def inspect(source_name: str) -> dict:
    """Count evidence, entity coverage and translation completeness without writes."""
    async with SessionFactory() as db:
        rows = (
            await db.scalars(
                select(Article)
                .join(Source, Source.id == Article.source_id)
                .where(Source.name == source_name)
            )
        ).all()
        ids = [row.id for row in rows]
        chunks = await db.scalar(
            select(func.count())
            .select_from(ArticleChunk)
            .where(ArticleChunk.article_id.in_(ids))
        )
        foreign = [row for row in rows if not row.language.startswith("zh")]
        return {
            "source": source_name,
            "articles": len(rows),
            "chunks": chunks,
            "with_minerals": sum(bool(row.minerals) for row in rows),
            "with_regions": sum(bool(row.regions) for row in rows),
            "with_companies": sum(bool(row.companies) for row in rows),
            "with_events": sum(row.event_id is not None for row in rows),
            "processed": sum(row.status in {"processed", "published"} for row in rows),
            "foreign_articles": len(foreign),
            "translated_foreign": sum(
                bool(row.title_zh and row.summary_zh and row.is_translated)
                for row in foreign
            ),
        }


def main() -> None:
    """Expose optional strict translation checks when an LLM is configured."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--require-translations", action="store_true")
    parser.add_argument("--require-entities", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = asyncio.run(inspect(args.source))
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    print(payload)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    if result["articles"] == 0:
        raise SystemExit(1)
    if (
        args.require_translations
        and result["translated_foreign"] != result["foreign_articles"]
    ):
        raise SystemExit(1)
    if args.require_entities and any(
        result[key] != result["articles"]
        for key in ("with_minerals", "with_regions", "with_companies")
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
