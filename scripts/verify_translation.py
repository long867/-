"""Exercise the configured translator against existing evidence without DB writes."""

import argparse
import asyncio
import json
from uuid import UUID

from app.core.db import SessionFactory
from app.models import Article
from pipeline.processors.translator import numeric_translation_valid, translate


async def run(article_id: UUID) -> None:
    """Load original text, close the transaction, then report validation outcomes."""
    async with SessionFactory() as db:
        article = await db.get(Article, article_id)
    if article is None:
        raise ValueError("Article not found")
    import pipeline.processors.translator as module

    original_complete = module.complete_json

    async def trace(system: str, prompt: str) -> dict:
        candidate = await original_complete(system, prompt)
        data = json.loads(prompt)
        if "text" not in data:
            print({"editorial": candidate}, flush=True)
        if "text" in data:
            print(
                {
                    "fragment_chars": len(data["text"]),
                    "input": data["text"],
                    "output": candidate,
                },
                flush=True,
            )
        return candidate

    module.complete_json = trace
    result = await translate(article.title, article.content, article.language)
    print(
        {
            "title": result["title_zh"],
            "summary": result["summary_zh"],
            "translated_characters": len(result["content_zh"] or ""),
            "numeric_validation": numeric_translation_valid(
                article.content, result["content_zh"] or ""
            ),
        }
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("article_id", type=UUID)
    asyncio.run(run(parser.parse_args().article_id))
