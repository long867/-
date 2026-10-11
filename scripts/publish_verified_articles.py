"""Publish reviewed real English evidence after deterministic translation checks."""

import argparse
import asyncio
import json

from sqlalchemy import select

from app.core.cache import invalidate_public_cache
from app.core.config import get_settings
from app.core.db import SessionFactory
from app.models import Article, Source
from app.rag.indexer import enqueue_sync
from pipeline.processors.translator import (
    numeric_translation_valid,
    summary_measurements_valid,
)


async def run(source_name: str, apply: bool) -> None:
    """Keep unprocessed, synthetic or inconsistent evidence private."""
    if get_settings().APP_ENV == "production":
        raise ValueError("Use authenticated administrative review in production")
    reviewed = []
    async with SessionFactory.begin() as db:
        articles = (
            await db.scalars(
                select(Article)
                .join(Source)
                .where(
                    Source.name == source_name,
                    Article.status == "processed",
                    Article.language == "en",
                )
            )
        ).all()
        for article in articles:
            if (
                article.url.startswith("https://example.com/")
                or not article.is_translated
                or not article.title_zh
                or not article.content_zh
                or not article.summary_zh
                or not 100 <= len(article.summary_zh) <= 200
                or not article.minerals
                or not article.regions
                or not numeric_translation_valid(article.content, article.content_zh)
                or not numeric_translation_valid(article.title, article.title_zh)
                or not summary_measurements_valid(
                    article.title + article.content, article.summary_zh
                )
            ):
                continue
            reviewed.append(
                {
                    "id": str(article.id),
                    "title": article.title_zh,
                    "numeric_validation": True,
                }
            )
            if apply:
                article.status = "published"
                await db.flush()
                await enqueue_sync(db, article)
    if apply:
        await invalidate_public_cache()
    print(
        json.dumps(
            {"source": source_name, "apply": apply, "reviewed": reviewed},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.source, args.apply))
