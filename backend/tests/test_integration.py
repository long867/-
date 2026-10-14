"""Run against PostgreSQL 16 + pgvector after `alembic upgrade head`."""

import os
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.db import get_db
from app.main import app
from app.models import (
    Article,
    ArticleChunk,
    ChatSession,
    Event,
    PipelineRun,
    Source,
    User,
)
from app.rag.retriever import HybridRetriever
from app.schemas.api import PriceInput
from app.services.prices import store_price
from pipeline.analyzers.events import cluster_article
from pipeline.fetchers.collect import Document, FetchBatch

pytestmark = pytest.mark.integration


async def test_incremental_dedup_counts_and_partial_checkpoint(monkeypatch) -> None:
    """Persist duplicates once and retain validators only on complete batches."""
    import app.tasks.ingest as module

    engine = create_async_engine(os.environ["TEST_DATABASE_URL"], poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(module, "SessionFactory", factory)
    source_id = uuid4()
    root = f"https://example.com/{source_id}"
    async with factory.begin() as db:
        db.add(
            Source(
                id=source_id,
                name="dedup-fixture",
                url=root + "/feed",
                type="rss",
                category="news",
            )
        )
    body = "BHP copper mine in Chile increased production by 12%. " * 10
    other = (
        "BHP reported a labor strike, suspended shipments and cut its output forecast. "
        "Negotiations will continue next week in Chile. " * 6
    )
    batch = FetchBatch(
        [
            Document(
                "BHP copper mine in Chile production update",
                body,
                root + "/a?utm_source=x",
            ),
            Document(
                "BHP copper mine in Chile production update", body, root + "/a?ref=home"
            ),
            Document(
                "BHP copper mine in Chile production update!", body, root + "/copy"
            ),
            Document(
                "BHP copper mine in Chile production updates",
                other,
                root + "/different-facts",
            ),
        ],
        etag='"v1"',
    )
    monkeypatch.setattr(module, "collect", AsyncMock(return_value=batch))
    try:
        result = await module.ingest_source(source_id, "dedup1", enqueue=False)
        assert (
            result["fetched"] == 4
            and result["new_articles"] == 2
            and result["duplicates"] == 2
        )
        async with factory() as db:
            source = await db.get(Source, source_id)
            assert source.etag == '"v1"'
        monkeypatch.setattr(
            module, "collect", AsyncMock(return_value=FetchBatch([], not_modified=True))
        )
        assert (await module.ingest_source(source_id, "dedup2", enqueue=False))[
            "new_articles"
        ] == 0
        monkeypatch.setattr(
            module,
            "collect",
            AsyncMock(
                return_value=FetchBatch(
                    [],
                    etag='"v2"',
                    errors=["web_article:ReadTimeout"],
                    state={"cursor": "uncommitted"},
                )
            ),
        )
        partial = await module.ingest_source(source_id, "dedup3", enqueue=False)
        assert partial["errors"] == 1 and partial["status"] == "partial"
        async with factory() as db:
            source = await db.get(Source, source_id)
            assert source.etag is None and source.fetch_state == {}
            runs = (
                await db.scalars(
                    select(PipelineRun)
                    .where(PipelineRun.source_id == source_id)
                    .order_by(PipelineRun.created_at)
                )
            ).all()
            assert runs[0].fetched_count == 4 and runs[0].new_count == 2
            assert runs[0].duplicate_count == 2 and runs[-1].error_count == 1
    finally:
        async with factory.begin() as db:
            await db.execute(delete(Article).where(Article.source_id == source_id))
            await db.execute(
                delete(PipelineRun).where(PipelineRun.source_id == source_id)
            )
            await db.execute(delete(Source).where(Source.id == source_id))
        await engine.dispose()


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"], poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await session.begin()
        yield session
        await session.rollback()
    await engine.dispose()


async def make_article(
    db, status: str = "published", *, scope: str | None = None
) -> Article:
    source = Source(
        name="test",
        url=f"https://example.com/{uuid4()}",
        type="rss",
        category="news",
        language="en",
    )
    db.add(source)
    await db.flush()
    content = (
        "Copper exports in Chile require permits. Supply was reported on 2026-10-09."
    )
    article = Article(
        source_id=source.id,
        title="Chile copper export policy",
        content=content,
        url=f"https://example.com/{uuid4()}",
        language="en",
        category="policy",
        status=status,
        minerals=["铜"],
        regions=["智利"] + ([scope] if scope else []),
        tags=[scope] if scope else [],
        quality_score=80,
        relevance_score=90,
        published_at=datetime.now(UTC),
    )
    db.add(article)
    await db.flush()
    db.add(
        ArticleChunk(
            article_id=article.id,
            chunk_index=0,
            text=content,
            search_text=content,
            start_char=0,
            end_char=len(content),
        )
    )
    await db.flush()
    return article


async def test_published_article_filters_and_pagination(db) -> None:
    # Isolate assertions from any real/demo corpus already in the test database.
    scope = str(uuid4())
    await make_article(db, "pending", scope=scope)
    visible = await make_article(db, scope=scope)

    async def override():
        yield db

    app.dependency_overrides[get_db] = override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/v1/articles?mineral=铜&region=智利&tag={scope}"
            )
            assert response.status_code == 200
            assert [row["id"] for row in response.json()["items"]] == [str(visible.id)]
            assert response.json()["total"] == 1
    finally:
        app.dependency_overrides.clear()


async def test_rag_uses_only_published_bilingual_evidence(db) -> None:
    scope = str(uuid4())
    visible = await make_article(db, scope=scope)
    await make_article(db, "processed", scope=scope)
    retriever = HybridRetriever(db, ["铜"], [scope])
    nodes = await retriever.aretrieve("智利的铜出口许可政策")
    assert len(nodes) == 1
    chunk, article = retriever.evidence[nodes[0].node.node_id]
    assert article.id == visible.id
    assert visible.content[chunk.start_char : chunk.end_char] == chunk.text


async def test_chat_ownership_and_non_admin_access(db, monkeypatch) -> None:
    import app.main as module
    from app.core.security import create_token

    monkeypatch.setattr(module, "limited", AsyncMock(return_value=False))
    first = User(email=f"{uuid4()}@example.com", password_hash="unused")
    second = User(email=f"{uuid4()}@example.com", password_hash="unused")
    db.add_all([first, second])
    await db.flush()
    session = ChatSession(user_id=first.id, title="private")
    db.add(session)
    await db.flush()

    async def override():
        yield db

    app.dependency_overrides[get_db] = override
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {create_token(second.id)}"},
        ) as client:
            assert (
                await client.get(f"/api/v1/chat/sessions/{session.id}")
            ).status_code == 404
            assert (
                await client.post(
                    "/api/v1/chat",
                    json={"session_id": str(session.id), "question": "铜价格如何"},
                )
            ).status_code == 404
            assert (await client.get("/api/v1/admin/sources")).status_code == 403
    finally:
        app.dependency_overrides.clear()


async def test_price_backfill_recalculates_same_series(db) -> None:
    from app.models import PriceRecord

    base = {
        "mineral": "铜",
        "unit": "吨",
        "currency": "USD",
        "source": f"https://example.com/{uuid4()}",
    }
    for date, price in [
        ("2026-10-10", "120"),
        ("2026-10-08", "100"),
        ("2026-10-09", "110"),
    ]:
        await store_price(db, PriceInput(**base, date=date, price=price))
    await store_price(db, PriceInput(**base, date="2026-10-09", price="110"))
    rows = (
        await db.scalars(
            select(PriceRecord)
            .where(PriceRecord.source == base["source"])
            .order_by(PriceRecord.date)
        )
    ).all()
    assert len(rows) == 3
    assert rows[0].change_pct is None
    assert rows[1].change_pct == Decimal("10.000000")
    assert rows[2].change_pct == Decimal("9.090909")
    await store_price(db, PriceInput(**base, date="2026-10-09", price="115"))
    assert rows[1].price == Decimal("115")
    assert rows[1].change_pct == Decimal("15.000000")
    assert rows[2].change_pct == Decimal("4.347826")


async def test_clustering_is_idempotent(db) -> None:
    article = await make_article(db)
    await cluster_article(db, article)
    await cluster_article(db, article)
    event = await db.get(Event, article.event_id)
    assert event.article_count == 1


async def test_admin_can_reprocess_reviewed_article_but_must_withdraw_published(
    db, monkeypatch
) -> None:
    """Processed rows can be translated later after public rows are withdrawn."""
    from types import SimpleNamespace

    from fastapi import HTTPException

    from app.api.routes import retry_article
    from app.core import task_dispatch

    article = await make_article(db, "processed")
    monkeypatch.setattr(db, "commit", AsyncMock())
    monkeypatch.setattr(
        task_dispatch,
        "enqueue_article",
        lambda *_: SimpleNamespace(id="fixture-job"),
    )
    result = await retry_article(article.id, db, SimpleNamespace(is_admin=True))
    assert article.status == "pending" and result["task_id"] == "fixture-job"
    article.status = "published"
    with pytest.raises(HTTPException) as error:
        await retry_article(article.id, db, SimpleNamespace(is_admin=True))
    assert error.value.status_code == 409


async def test_source_replay_does_not_duplicate_articles(monkeypatch) -> None:
    import app.tasks.ingest as module

    engine = create_async_engine(os.environ["TEST_DATABASE_URL"], poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(module, "SessionFactory", factory)
    source_id = uuid4()
    async with factory.begin() as session:
        session.add(
            Source(
                id=source_id,
                name="replay",
                url=f"https://example.com/{uuid4()}",
                type="rss",
                category="news",
                language="en",
            )
        )
    batch = FetchBatch(
        [
            Document(
                "Copper policy",
                "Copper policy requires permits.",
                f"https://example.com/{uuid4()}",
            )
        ],
        etag='"v2"',
    )
    monkeypatch.setattr(module, "collect", AsyncMock(return_value=batch))
    monkeypatch.setattr(module, "enqueue_article", lambda *_: None)
    try:
        first = await module.ingest_source(source_id, "job1")
        second = await module.ingest_source(source_id, "job2")
        assert first["new_articles"] == 1 and second["new_articles"] == 0
        async with factory() as session:
            count = await session.scalar(
                select(func.count())
                .select_from(Article)
                .where(Article.source_id == source_id)
            )
            assert count == 1
            assert (await session.get(Source, source_id)).etag == '"v2"'
    finally:
        async with factory.begin() as session:
            await session.execute(delete(Article).where(Article.source_id == source_id))
            await session.execute(
                delete(PipelineRun).where(PipelineRun.source_id == source_id)
            )
            await session.execute(delete(Source).where(Source.id == source_id))
        await engine.dispose()


async def test_full_english_processing_with_explicit_llm_fixture(monkeypatch) -> None:
    """Verify persisted translations, original chunks, entities and event membership."""
    import app.tasks.ingest as module
    import pipeline.processors.extractor as extractor
    import pipeline.processors.translator as translator
    from app.core.config import Settings

    engine = create_async_engine(os.environ["TEST_DATABASE_URL"], poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(module, "SessionFactory", factory)
    settings = Settings(LLM_API_KEY="test-fixture", _env_file=None)
    monkeypatch.setattr(translator, "get_settings", lambda: settings)
    monkeypatch.setattr(extractor, "get_settings", lambda: settings)
    body = "BHP copper production in Chile increased 12%. " * 10
    summary = (
        "BHP披露智利铜矿生产信息，铜产量增长12%。报道涉及公司的矿山运营和铜供应变化，"
        "这一数据有助于跟踪相关项目生产情况。资料没有披露新的建设进度、投资金额或未来产能，"
        "不能据此确定后续铜价表现。以上摘要仅整理原文给出的公司、国家、矿种和产量数据。"
    )
    monkeypatch.setattr(
        translator,
        "complete_json",
        AsyncMock(
            side_effect=[
                {
                    "title_zh": "BHP智利铜矿产量增长",
                    "summary": "BHP copper production increased 12% in Chile.",
                    "summary_zh": summary,
                },
                {"content_zh": "BHP在智利的铜产量增长12%。" * 10},
            ]
        ),
    )
    monkeypatch.setattr(
        extractor,
        "complete_json",
        AsyncMock(
            return_value={
                "minerals": ["铜"],
                "regions": ["智利"],
                "companies": ["BHP", "Invented Mining"],
                "projects": [],
                "policies": [],
                "category": "news",
                "relevance_score": 0.96,
            }
        ),
    )
    source_id, article_id = uuid4(), uuid4()
    event_id = None
    async with factory.begin() as db:
        db.add(
            Source(
                id=source_id,
                name="llm-fixture",
                url=f"https://example.com/{source_id}",
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
                title="BHP copper production in Chile",
                content=body,
                url=f"https://example.com/{article_id}",
                category="news",
                language="en",
                published_at=datetime.now(UTC),
            )
        )
    try:
        assert (await module.process_one(article_id))["status"] == "processed"
        async with factory() as db:
            article = await db.get(Article, article_id)
            event_id = article.event_id
            assert article.title == "BHP copper production in Chile"
            assert (
                article.is_translated
                and article.title_zh
                and 100 <= len(article.summary_zh) <= 200
            )
            assert article.minerals == ["铜"] and article.regions == ["智利"]
            assert article.companies == ["BHP"] and article.relevance_score == 96
            chunks = (
                await db.scalars(
                    select(ArticleChunk).where(ArticleChunk.article_id == article_id)
                )
            ).all()
            assert chunks and all(
                body[row.start_char : row.end_char] == row.text for row in chunks
            )
            assert (await db.get(Event, event_id)).article_count == 1
    finally:
        async with factory.begin() as db:
            await db.execute(delete(Article).where(Article.id == article_id))
            if event_id:
                await db.execute(delete(Event).where(Event.id == event_id))
            await db.execute(delete(Source).where(Source.id == source_id))
        await engine.dispose()


async def test_feed_fallback_can_upgrade_to_full_text_before_publication(
    monkeypatch,
) -> None:
    """Retry detail fetching without duplicating rows or rewriting public evidence."""
    import app.tasks.ingest as module

    engine = create_async_engine(os.environ["TEST_DATABASE_URL"], poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(module, "SessionFactory", factory)
    source_id, article_id = uuid4(), uuid4()
    root = f"https://example.com/{source_id}"
    async with factory.begin() as db:
        db.add(
            Source(
                id=source_id,
                name="fulltext-fixture",
                url=root + "/feed",
                type="rss",
                category="news",
            )
        )
        await db.flush()
        db.add(
            Article(
                id=article_id,
                source_id=source_id,
                title="Copper",
                content="Feed snippet.",
                url=root + "/article",
                category="news",
                language="en",
                status="processed",
                raw_json={"full_text": False},
            )
        )
    monkeypatch.setattr(
        module,
        "collect",
        AsyncMock(
            return_value=FetchBatch(
                [
                    Document(
                        "Copper",
                        "Full original copper article.",
                        root + "/article",
                        metadata={"full_text": True},
                    )
                ]
            )
        ),
    )
    try:
        result = await module.ingest_source(source_id, "upgrade1", enqueue=False)
        assert result["new_articles"] == 0 and result["upgraded_articles"] == 1
        assert result["article_ids"] == [str(article_id)]
        async with factory.begin() as db:
            row = await db.get(Article, article_id)
            assert (
                row.content == "Full original copper article."
                and row.status == "pending"
            )
            row.status = "published"
            row.raw_json = {"full_text": False}
        assert (await module.ingest_source(source_id, "upgrade2", enqueue=False))[
            "upgraded_articles"
        ] == 0
    finally:
        async with factory.begin() as db:
            await db.execute(delete(Article).where(Article.id == article_id))
            await db.execute(
                delete(PipelineRun).where(PipelineRun.source_id == source_id)
            )
            await db.execute(delete(Source).where(Source.id == source_id))
        await engine.dispose()
