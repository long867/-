"""Archive bounds and independent-source editorial evidence gates."""

import os
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.models import Article, ArticleChunk, Source
from app.rag.retriever import HybridRetriever
from pipeline.fetchers.rss_fetcher import RSSFetcher
from pipeline.import_backfill import validate_record
from pipeline.processors.backfill import EditorialDocument, validate_editorial
from pipeline.processors.translator import (
    number_words,
    numeric_translation_valid,
    summary_measurements_valid,
)
from pipeline.schemas import RawArticle, SourceDefinition


def test_spanish_evidence_preserves_counts_units_magnitudes_and_currency():
    """Regional sources must pass faithful translations, never changed quantities."""
    assert numeric_translation_valid(
        "Cuatro nuevas plantas de litio", "4座新锂工厂", "es"
    )
    assert not numeric_translation_valid(
        "Cuatro nuevas plantas de litio", "5座新锂工厂", "es"
    )
    assert not number_words("un proyecto y una compañía", "es")
    assert not number_words("Once again, mining resumed", "en")
    assert numeric_translation_valid("Once plantas", "11座工厂", "es-MX")
    assert not numeric_translation_valid(
        "Once again mining resumed", "矿山再次运营11次", "en"
    )
    assert summary_measurements_valid("rampa de 267 metros", "矿山连接巷道长267米")
    assert summary_measurements_valid("3.4 millones de onzas", "3.4百万盎司")
    assert summary_measurements_valid("dos toneladas", "2吨", "es")
    assert not summary_measurements_valid("3.4 millones de onzas", "3.4十亿盎司")
    assert not summary_measurements_valid("267 metros", "267千米")
    assert summary_measurements_valid("7 dólares canadienses", "7加元")
    assert not summary_measurements_valid("7 dólares canadienses", "7美元")
    assert not summary_measurements_valid("7 dólares", "7美元")
    assert not summary_measurements_valid("267 Metropolitan shares", "267米")


def feed_response(url: str, links: list[str]) -> httpx.Response:
    """Create a small RSS response with original article evidence."""
    entries = "".join(
        f"<item><title>Copper project {index}</title><link>{link}</link>"
        "<description>Copper mining project in Canada.</description></item>"
        for index, link in enumerate(links)
    )
    return httpx.Response(
        200,
        request=httpx.Request("GET", url),
        content=f'<rss version="2.0"><channel>{entries}</channel></rss>'.encode(),
    )


async def test_archive_stops_when_provider_repeats_page() -> None:
    source = SourceDefinition(
        name="Archive",
        url="https://example.com/feed/",
        type="rss",
        category="news",
        authority_score=8,
        parser_config={
            "fetch_full_content": False,
            "max_items": 20,
            "pagination": {"mode": "page", "max_pages": 10, "param": "paged"},
        },
    )
    first = feed_response(source.url, ["https://example.com/a"])
    second = feed_response(source.url + "?paged=2", ["https://example.com/b"])
    repeated = feed_response(source.url + "?paged=3", ["https://example.com/b"])
    transport = AsyncMock()
    transport.get.side_effect = [first, second, repeated]
    collector = RSSFetcher(source, transport)
    rows = await collector.fetch()
    assert [row.url for row in rows] == [
        "https://example.com/a",
        "https://example.com/b",
    ]
    assert transport.get.await_count == 3
    assert not collector.result.errors


async def test_archive_preserves_first_page_on_later_failure() -> None:
    source = SourceDefinition(
        name="Archive",
        url="https://example.com/feed/",
        type="rss",
        category="news",
        authority_score=8,
        parser_config={
            "fetch_full_content": False,
            "pagination": {"mode": "page", "max_pages": 3},
        },
    )
    transport = AsyncMock()
    transport.get.side_effect = [
        feed_response(source.url, ["https://example.com/a"]),
        httpx.ConnectError("Network unavailable"),
    ]
    collector = RSSFetcher(source, transport)
    assert len(await collector.fetch()) == 1
    assert collector.result.errors == ["rss_page:ConnectError"]


def test_editorial_rejects_other_article_price_and_keeps_original_body(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ENTITY_MATCHER", "dictionary")
    source = SourceDefinition(
        name="Mine news",
        url="https://example.com/feed",
        type="rss",
        category="news",
        authority_score=8,
    )
    row = RawArticle(
        source_name=source.name,
        url="https://example.com/news",
        title="Copper price 9000 USD",
        content="Acme Copper reports a copper price of 9000 USD in Canada.",
        language="en",
        category="news",
    )
    document = EditorialDocument(row, source)
    candidate = {
        "title_zh": "铜价9000 USD",
        "summary_zh": "加拿大铜矿企业公布了铜产品报价，"
        "原文涉及当地市场及该企业的经营信息。"
        "这条报道提供的是一次报价观察，读者可以沿原文链接核实其具体背景与发布时间。"
        "资料未提供连续历史报价，因此不能仅凭这条记录推断整个市场的长期趋势。",
        "companies": ["Acme Copper", "Invented Corp"],
    }
    values = validate_editorial(document, candidate, {})
    assert values["companies"] == ["Acme Copper"]
    assert values["minerals"] == ["铜"]
    assert values["content_zh"] is None
    assert not values["is_translated"]
    candidate["summary_zh"] = candidate["summary_zh"] + "最新价格为12000 USD。"
    with pytest.raises(ValueError, match="unsupported numeric"):
        validate_editorial(document, candidate, {})


@pytest.mark.integration
async def test_backfill_publishes_once_with_exact_retrievable_evidence(
    monkeypatch,
) -> None:
    """An imported document is immediately searchable with unchanged citations."""
    import pipeline.import_backfill as module

    monkeypatch.setenv("ENTITY_MATCHER", "dictionary")
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"], poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(module, "SessionFactory", factory)
    root = "https://example.com/" + uuid4().hex
    source = SourceDefinition(
        name="ARCHIVE TEST FIXTURE",
        url=root + "/feed",
        type="rss",
        category="news",
        authority_score=8,
    )
    original = (
        "Example Copper selected Verifiable Drilling for its copper project "
        "in Canada. The drilling programme covers 9000 metres. "
    ) * 9 + root
    raw = RawArticle(
        source_name=source.name,
        url=root + "/article?utm_source=test",
        title="Copper exploration update",
        content=original,
        language="en",
        category="news",
    )
    candidate = {
        "title_zh": "加拿大铜矿勘探项目公布钻探计划",
        "summary_zh": "加拿大铜矿项目公布了钻探计划，企业选择了钻探承包商。"
        "原文介绍了项目主体、钻探范围以及承包安排，提供了一条可以追溯到发布方的项目进展记录。"
        "这些信息反映的是一次勘探计划更新，原文没有提供该项目的产量或市场价格预测。"
        "读者可以沿原文链接核实其计划详情。",
        "companies": ["Example Copper", "Verifiable Drilling"],
    }
    enriched = validate_editorial(EditorialDocument(raw, source), candidate, {})
    value = {
        "source": source.model_dump(mode="json"),
        "article": raw.model_dump(mode="json"),
        "enriched": enriched,
    }
    try:
        assert await module.import_record(value, publish=True) == "published"
        assert await module.import_record(value, publish=True) == "duplicate"
        async with factory() as db:
            source_id = await db.scalar(
                select(Source.id).where(Source.url == source.url)
            )
            assert (
                await db.scalar(
                    select(func.count())
                    .select_from(Article)
                    .where(Article.source_id == source_id)
                )
                == 1
            )
            article = await db.scalar(
                select(Article).where(Article.source_id == source_id)
            )
            chunks = list(
                (
                    await db.scalars(
                        select(ArticleChunk).where(
                            ArticleChunk.article_id == article.id
                        )
                    )
                ).all()
            )
            assert chunks and all(
                chunk.text == original[chunk.start_char : chunk.end_char]
                for chunk in chunks
            )
            assert article.status == "published" and article.embedding is None
            assert article.content_zh is None and not article.is_translated
            retriever = HybridRetriever(db, minerals=["铜"], regions=["加拿大"])
            nodes = await retriever.aretrieve("Verifiable Drilling 加拿大铜矿")
            assert any(
                node.node.metadata["article_id"] == str(article.id) for node in nodes
            )
        altered = value | {
            "enriched": enriched
            | {"summary_zh": enriched["summary_zh"] + "最新价格10000 USD。"}
        }
        with pytest.raises(ValueError, match="unsupported numbers"):
            validate_record(altered)
    finally:
        async with factory.begin() as db:
            source_id = await db.scalar(
                select(Source.id).where(Source.url == source.url)
            )
            if source_id:
                await db.execute(delete(Article).where(Article.source_id == source_id))
                await db.execute(delete(Source).where(Source.id == source_id))
        await engine.dispose()
