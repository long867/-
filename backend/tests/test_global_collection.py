"""Grounded multilingual ingestion and publication without full-body translation."""

import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.models import Article, ArticleChunk, Event, Source
from pipeline.processors.entities import extract_entities


def test_latin_american_and_african_aliases(monkeypatch) -> None:
    """Canonical tags follow actual multilingual evidence, not publisher location."""
    monkeypatch.setenv("ENTITY_MATCHER", "dictionary")
    result = extract_entities(
        "Producción de cobre y plata en Perú; "
        "ouro e minério de ferro no Brasil; gold in Zimbabwe."
    )
    assert {"铜", "银", "金", "铁矿石"} <= set(result["minerals"])
    assert {"秘鲁", "巴西", "津巴布韦"} <= set(result["regions"])
    assert (
        "几内亚"
        not in extract_entities("Copper project in Papua New Guinea.")["regions"]
    )


@pytest.mark.integration
async def test_editorial_auto_publish_keeps_exact_original_evidence(
    monkeypatch,
) -> None:
    """Validated Chinese titles/summaries can publish while bodies stay original."""
    import app.tasks.ingest as ingest
    import pipeline.processors.backfill as editorial
    import pipeline.processors.enrich as enrichment

    settings = Settings(
        ENRICHMENT_MODE="editorial",
        AUTO_PUBLISH=True,
        ENTITY_MATCHER="dictionary",
        ML_ENABLED=False,
        PUBLISH_QUALITY_THRESHOLD=50,
        _env_file=None,
    )
    monkeypatch.setattr(ingest, "get_settings", lambda: settings)
    monkeypatch.setattr(enrichment, "get_settings", lambda: settings)
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"], poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(ingest, "SessionFactory", factory)
    body = "BHP reports copper production growth of 12% in Chile. " * 12
    source_id, article_id = uuid4(), uuid4()
    url = f"https://example.com/{article_id}"
    summary = (
        "BHP披露智利铜矿生产情况，原文所述铜产量增长12%。"
        "这条资讯涉及公司的铜矿经营活动和相关生产表现，"
        "提供了可以追溯到原文的产量变化依据。"
        "资料围绕智利、BHP和铜产品展开，没有提供连续历史报价或未来铜价预测，"
        "不能将这一次产量增长直接视为价格上涨结论。"
    )
    model = AsyncMock(
        return_value={
            "items": [
                {
                    "id": "doc-1",
                    "title_zh": "BHP智利铜矿产量增长12%",
                    "summary_zh": summary,
                    "companies": ["BHP"],
                    "category": "news",
                }
            ]
        }
    )
    monkeypatch.setattr(editorial, "complete_json", model)
    monkeypatch.setattr(
        ingest, "embed", AsyncMock(side_effect=lambda texts: [None] * len(texts))
    )
    async with factory.begin() as db:
        db.add(
            Source(
                id=source_id,
                name="official fixture",
                url=f"https://example.com/{source_id}/feed",
                type="rss",
                category="news",
                authority_score=9,
            )
        )
        await db.flush()
        db.add(
            Article(
                id=article_id,
                source_id=source_id,
                title="BHP copper growth 12% in Chile",
                content=body,
                url=url,
                category="news",
                language="en",
                published_at=datetime.now(UTC),
            )
        )
    event_id = None
    try:
        assert (await ingest.process_one(article_id))["status"] == "published"
        assert (await ingest.process_one(article_id))["status"] == "skipped"
        assert model.await_count == 1
        async with factory() as db:
            row = await db.get(Article, article_id)
            event_id = row.event_id
            assert not row.is_translated and row.content_zh is None
            assert row.raw_json["body_translation"] == "original"
            assert row.minerals == ["铜"] and row.regions == ["智利"]
            chunks = (
                await db.scalars(
                    select(ArticleChunk).where(ArticleChunk.article_id == article_id)
                )
            ).all()
            assert chunks and all(
                body[c.start_char : c.end_char] == c.text for c in chunks
            )
            assert all(summary in c.search_text for c in chunks)
    finally:
        async with factory.begin() as db:
            await db.execute(delete(Article).where(Article.id == article_id))
            if event_id:
                await db.execute(delete(Event).where(Event.id == event_id))
            await db.execute(delete(Source).where(Source.id == source_id))
        await engine.dispose()


@pytest.mark.integration
async def test_archive_seeding_is_pending_and_idempotent(monkeypatch) -> None:
    """Unprocessed evidence never enters public retrieval or activates a feed."""
    import pipeline.seed_archive as seed

    engine = create_async_engine(os.environ["TEST_DATABASE_URL"], poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(seed, "SessionFactory", factory)
    root = f"https://example.com/{uuid4()}"
    value = {
        "source": {
            "name": "archive fixture",
            "url": root + "/feed",
            "type": "rss",
            "category": "news",
            "authority_score": 8,
        },
        "article": {
            "source_name": "archive fixture",
            "url": root + "/article?utm_source=x",
            "title": "Copper project in Peru",
            "content": "Copper project in Peru reports drilling. " * 8,
            "language": "en",
            "category": "news",
        },
    }
    source_id = None
    try:
        assert await seed.seed_record(value) == "pending"
        assert await seed.seed_record(value) == "duplicate"
        async with factory() as db:
            row = await db.scalar(
                select(Article).where(Article.url == root + "/article")
            )
            source_id = row.source_id
            assert row.status == "pending" and row.embedding is None
            assert row.published_at is None and row.summary_zh is None
            assert row.raw_json["initialization_requested"] is True
            assert not (await db.get(Source, source_id)).active
            assert not (
                await db.scalars(
                    select(ArticleChunk).where(ArticleChunk.article_id == row.id)
                )
            ).all()
    finally:
        async with factory.begin() as db:
            if source_id:
                await db.execute(delete(Article).where(Article.source_id == source_id))
                await db.execute(delete(Source).where(Source.id == source_id))
        await engine.dispose()
