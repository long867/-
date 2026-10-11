"""Persist non-secret evidence about the actual collected and published corpus."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from app.core.db import SessionFactory
from app.models import Article, PriceRecord, Source
from sqlalchemy import func, select

from pipeline.processors.translator import numeric_translation_valid


async def run() -> None:
    """Snapshot actual counts, numerical gates, provenance and vector dimensions."""
    async with SessionFactory() as db:
        rows = (await db.execute(select(Article, Source.name).join(Source))).all()
        prices = (
            await db.scalars(select(PriceRecord).order_by(PriceRecord.date))
        ).all()
        dimensions = (
            await db.scalars(
                select(func.vector_dims(Article.embedding))
                .where(Article.embedding.is_not(None))
                .distinct()
            )
        ).all()
    assert all(not item.url.startswith("https://example.com/") for item, _ in rows)
    assert all(not item.source.startswith("https://example.com/") for item in prices)
    foreign = [
        item for item, _ in rows if item.language == "en" and item.status == "published"
    ]
    assert all(
        item.title_zh and item.summary_zh and item.is_translated for item in foreign
    )
    assert all(
        numeric_translation_valid(item.content, item.content_zh) for item in foreign
    )
    result = {
        "checked_at": datetime.now(UTC).isoformat(),
        "articles": len(rows),
        "published": sum(item.status == "published" for item, _ in rows),
        "pending": sum(item.status == "pending" for item, _ in rows),
        "published_english": len(foreign),
        "all_published_english_numeric_checks": True,
        "prices": len(prices),
        "vector_dimensions": dimensions,
        "latest_quote": {
            "date": str(prices[-1].date),
            "price": str(prices[-1].price),
            "unit": prices[-1].unit,
            "currency": prices[-1].currency,
            "product": prices[-1].product,
            "source_url": prices[-1].source_url,
        },
        "news": [
            {
                "title": item.title_zh,
                "url": item.url,
                "summary_characters": len(item.summary_zh),
            }
            for item in foreign
        ],
    }
    target = (
        Path(__file__).resolve().parents[1] / "docs" / "phase3-data-verification.json"
    )
    target.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(run())
