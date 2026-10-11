"""Database acceptance with isolated, explicitly synthetic article fixtures."""

import json
import os
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from qdrant_client import AsyncQdrantClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.core.db import get_db
from app.core.security import create_token
from app.main import app
from app.models import Article, ArticleChunk, ChatSession, Source, User, VectorSyncJob
from app.rag.qdrant_store import QdrantStore
from app.rag.retriever import HybridRetriever

pytestmark = pytest.mark.integration
VECTOR = [1.0] + [0.0] * 1023  # Injected test vector; never a runtime fallback.
BODY = "TEST FIXTURE: Lithium price rose from 100 to 110 USD/t in 2026 in Australia."


@pytest_asyncio.fixture
async def state():
    """Commit only UUID-scoped test records, then remove exactly those records."""
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"], poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    source_id, user_id, other_id = uuid4(), uuid4(), uuid4()
    article_ids = []
    async with factory.begin() as db:
        db.add(
            Source(
                id=source_id,
                name="RAG 测试信源（虚构）",
                url=f"https://example.com/test/{source_id}",
                type="rss",
                category="price",
                language="en",
            )
        )
        db.add_all(
            [
                User(id=user_id, email=f"{user_id}@example.com", password_hash="test"),
                User(
                    id=other_id, email=f"{other_id}@example.com", password_hash="test"
                ),
            ]
        )
        await db.flush()
        for status, mineral, year, content in [
            ("published", "锂", 2026, BODY),
            ("processed", "锂", 2026, BODY),
            ("published", "锂", 2025, BODY.replace("2026", "2025")),
            ("published", "铜", 2026, BODY.replace("Lithium", "Copper")),
            (
                "published",
                "锂",
                2026,
                "TEST FIXTURE: Lithium project analysis must verify the price "
                "basis and publication date; no market observation is provided.",
            ),
        ]:
            article_id = uuid4()
            article_ids.append(article_id)
            db.add(
                Article(
                    id=article_id,
                    source_id=source_id,
                    title="TEST FIXTURE: " + mineral,
                    title_zh="测试：" + mineral + "行业数据",
                    summary_zh="仅限自动化测试",
                    content=content,
                    content_zh="【虚构测试资料】" + content,
                    url=f"https://example.com/test/{article_id}",
                    category="price",
                    language="en",
                    is_translated=True,
                    status=status,
                    minerals=[mineral],
                    regions=["澳大利亚", "test-" + str(source_id)],
                    companies=["Albemarle"],
                    published_at=datetime(year, 1, 2, tzinfo=UTC),
                )
            )
            await db.flush()
            db.add(
                ArticleChunk(
                    article_id=article_id,
                    chunk_index=0,
                    text=content,
                    search_text=content,
                    start_char=0,
                    end_char=len(content),
                )
            )
    try:
        yield factory, source_id, user_id, other_id, article_ids
    finally:
        app.dependency_overrides.clear()
        async with factory.begin() as db:
            await db.execute(delete(User).where(User.id.in_([user_id, other_id])))
            await db.execute(delete(Article).where(Article.source_id == source_id))
            await db.execute(delete(Source).where(Source.id == source_id))
        await engine.dispose()


async def test_index_is_incremental_and_preserves_citation_spans(state, monkeypatch):
    import app.rag.indexer as module

    factory, _, _, _, article_ids = state
    monkeypatch.setattr(module, "SessionFactory", factory)
    monkeypatch.setattr(module, "get_settings", lambda: Settings(ML_ENABLED=True))
    encoder = AsyncMock(side_effect=lambda texts, **_: [VECTOR] * len(texts))
    monkeypatch.setattr(module, "embed", encoder)
    assert await module.index_article(article_ids[0]) == "indexed"
    async with factory() as db:
        chunk = await db.scalar(
            select(ArticleChunk).where(ArticleChunk.article_id == article_ids[0])
        )
        chunk_id = chunk.id
        assert BODY[chunk.start_char : chunk.end_char] == chunk.text
        article = await db.get(Article, article_ids[0])
        assert len(article.embedding) == 1024
        assert article.indexed_at >= article.updated_at
    assert article_ids[0] not in await module.pending_ids(1000)
    assert await module.index_article(article_ids[0]) == "unchanged"
    assert encoder.await_count == 1 and encoder.await_args.kwargs["max_tokens"] == 512
    async with factory() as db:
        assert (
            await db.scalar(
                select(ArticleChunk).where(ArticleChunk.article_id == article_ids[0])
            )
        ).id == chunk_id
        assert (
            await db.get(VectorSyncJob, article_ids[0])
        ).revision == article.embedding_hash


async def test_encoding_snapshot_race_does_not_commit_stale_vectors(state, monkeypatch):
    import app.rag.indexer as module

    factory, _, _, _, article_ids = state
    monkeypatch.setattr(module, "SessionFactory", factory)
    monkeypatch.setattr(module, "get_settings", lambda: Settings(ML_ENABLED=True))

    async def encode_and_edit(texts, **_):
        async with factory.begin() as db:
            item = await db.get(Article, article_ids[0])
            item.content_zh = "文章在编码期间被编辑"
        return [VECTOR] * len(texts)

    monkeypatch.setattr(module, "embed", encode_and_edit)
    assert await module.index_article(article_ids[0]) == "stale"
    async with factory() as db:
        assert (await db.get(Article, article_ids[0])).indexed_at is None
        assert await db.get(VectorSyncJob, article_ids[0]) is None


async def test_untranslated_articles_do_not_block_incremental_dispatch(
    state, monkeypatch
):
    """Exclude missing or blank Chinese bodies before applying the batch limit."""
    import app.rag.indexer as module

    factory, _, _, _, article_ids = state
    monkeypatch.setattr(module, "SessionFactory", factory)
    monkeypatch.setattr(module, "get_settings", lambda: Settings(ML_ENABLED=True))
    async with factory.begin() as db:
        first = await db.get(Article, article_ids[0])
        first.title_zh = first.content_zh = None
        second = await db.get(Article, article_ids[1])
        second.content_zh = "   "
    pending = await module.pending_ids(1000)
    assert article_ids[0] not in pending and article_ids[1] not in pending
    assert set(article_ids[2:]).issubset(pending)
    assert await module.index_article(article_ids[0]) == "untranslated"
    assert await module.index_article(article_ids[1]) == "untranslated"


async def test_translation_backfill_is_previewable_and_preserves_review(
    state, monkeypatch
):
    """Recover pre-key work without reopening published rows or losing raw text."""
    import pipeline.reprocess as module

    factory, _, _, _, article_ids = state
    monkeypatch.setattr(module, "SessionFactory", factory)
    monkeypatch.setattr(module, "get_settings", lambda: Settings(LLM_API_KEY="test"))
    async with factory.begin() as db:
        article = await db.get(Article, article_ids[1])
        article.is_translated = False
        article.title_zh = article.content_zh = None
    preview = await module.run(article_id=article_ids[1], dry_run=True)
    assert preview["candidates"] == 1 and preview["processed"] == 0
    assert not (await module.run(article_id=article_ids[0], dry_run=True))["candidates"]
    async with factory() as db:
        assert (await db.get(Article, article_ids[1])).status == "processed"
    monkeypatch.setattr(module, "process_one", AsyncMock(side_effect=TimeoutError()))
    outcome = await module.run(article_id=article_ids[1])
    assert outcome["errors"] == 1
    async with factory() as db:
        article = await db.get(Article, article_ids[1])
        assert (
            article.status == "pending" and article.processing_error == "TimeoutError"
        )
        assert article.content == BODY
        assert (await db.get(Article, article_ids[0])).status == "published"


async def test_full_rebuild_is_idempotent_and_source_scoped(state, monkeypatch):
    import app.rag.indexer as module

    factory, source_id, _, _, article_ids = state
    monkeypatch.setattr(module, "SessionFactory", factory)
    monkeypatch.setattr(module, "get_settings", lambda: Settings(ML_ENABLED=True))
    monkeypatch.setattr(
        module, "embed", AsyncMock(side_effect=lambda texts, **_: [VECTOR] * len(texts))
    )
    assert await module.rebuild(batch_size=2, source_id=source_id) == {"indexed": 5}
    assert await module.rebuild(batch_size=2, source_id=source_id) == {"indexed": 5}
    async with factory() as db:
        assert (
            await db.scalar(
                select(func.count())
                .select_from(ArticleChunk)
                .where(ArticleChunk.article_id.in_(article_ids))
            )
            == 5
        )
        assert (
            await db.scalar(
                select(func.count())
                .select_from(VectorSyncJob)
                .where(VectorSyncJob.article_id.in_(article_ids))
            )
            == 5
        )


async def test_qdrant_failure_preserves_pg_vectors_and_retries(state, monkeypatch):
    import app.rag.indexer as module

    factory, _, _, _, article_ids = state
    monkeypatch.setattr(module, "SessionFactory", factory)
    monkeypatch.setattr(module, "get_settings", lambda: Settings(ML_ENABLED=True))
    monkeypatch.setattr(
        module, "embed", AsyncMock(side_effect=lambda texts, **_: [VECTOR] * len(texts))
    )
    await module.index_article(article_ids[0])
    client = (
        AsyncQdrantClient(url=os.environ["TEST_QDRANT_URL"])
        if os.getenv("TEST_QDRANT_URL")
        else AsyncQdrantClient(":memory:")
    )
    store = QdrantStore(client)
    store.articles = "miningintel_test_" + uuid4().hex
    store.chunks = store.articles + "_chunks"
    original = store.replace_article
    monkeypatch.setattr(store, "replace_article", AsyncMock(side_effect=TimeoutError()))
    try:
        assert await module.sync_outbox(store=store, article_id=article_ids[0]) == {
            "synced": 0,
            "errors": 1,
        }
        async with factory.begin() as db:
            job = await db.get(VectorSyncJob, article_ids[0])
            assert job.attempts == 1 and job.last_error == "TimeoutError"
            assert (await db.get(Article, article_ids[0])).embedding is not None
            job.next_retry_at = datetime(2020, 1, 1, tzinfo=UTC)
        monkeypatch.setattr(store, "replace_article", original)
        assert await module.sync_outbox(store=store, article_id=article_ids[0]) == {
            "synced": 1,
            "errors": 0,
        }
        async with factory() as db:
            assert await db.get(VectorSyncJob, article_ids[0]) is None
        assert (await client.count(store.articles)).count == 1
        assert (await client.count(store.chunks)).count == 1
    finally:
        if os.getenv("TEST_QDRANT_URL"):
            await client.delete_collection(store.chunks)
            await client.delete_collection(store.articles)
        await client.close()


async def test_price_retrieval_pre_filters_date_mineral_and_visibility(
    state, monkeypatch
):
    import app.rag.retriever as module

    factory, _, _, _, article_ids = state
    monkeypatch.setattr(module, "embed", AsyncMock(return_value=[None]))
    monkeypatch.setattr(module, "rerank", AsyncMock(return_value=None))
    async with factory() as db:
        nodes = await HybridRetriever(
            db,
            ["锂"],
            ["澳大利亚"],
            category="price",
            start=datetime(2026, 1, 1, tzinfo=UTC),
            end=datetime(2027, 1, 1, tzinfo=UTC),
        ).aretrieve("2026年锂矿价格走势如何")
        matching = [
            node for node in nodes if node.metadata["article_id"] == str(article_ids[0])
        ]
        assert len(matching) == 1
        assert all(
            node.metadata["article_id"] not in map(str, article_ids[1:])
            for node in nodes
        )
        assert matching[0].metadata["source_name"] == "RAG 测试信源（虚构）"


async def test_verified_table_quote_with_separate_unit_note_is_retrievable(
    state, monkeypatch
):
    import app.rag.retriever as module

    factory, source_id, _, _, article_ids = state
    body = "【虚构测试】现货价格表：碳酸锂 121000.00。单位说明：元/吨。"
    async with factory.begin() as db:
        article = await db.get(Article, article_ids[0])
        article.content = body
        article.raw_json = {
            "price_observation": {
                "price": "121000.00",
                "currency": "CNY",
                "unit": "吨",
                "date": "2026-01-02",
            }
        }
        chunk = await db.scalar(
            select(ArticleChunk).where(ArticleChunk.article_id == article.id)
        )
        chunk.text, chunk.search_text, chunk.end_char = body, body, len(body)
    monkeypatch.setattr(module, "embed", AsyncMock(return_value=[None]))
    monkeypatch.setattr(module, "rerank", AsyncMock(return_value=None))
    async with factory() as db:
        nodes = await HybridRetriever(db, ["锂"], ["test-" + str(source_id)]).aretrieve(
            "碳酸锂现货报价是多少"
        )
        assert str(article_ids[0]) in [n.metadata["article_id"] for n in nodes]
        assert str(article_ids[4]) not in [n.metadata["article_id"] for n in nodes]


async def test_pgvector_recalls_a_passage_without_keyword_overlap(state, monkeypatch):
    """Exercise SQL cosine retrieval independently of lexical matching."""
    import app.rag.indexer as indexing
    import app.rag.retriever as retrieval

    factory, source_id, _, _, article_ids = state
    settings = Settings(ML_ENABLED=True, QDRANT_URL=None)
    monkeypatch.setattr(indexing, "SessionFactory", factory)
    monkeypatch.setattr(indexing, "get_settings", lambda: settings)
    monkeypatch.setattr(
        indexing,
        "embed",
        AsyncMock(side_effect=lambda texts, **_: [VECTOR] * len(texts)),
    )
    assert await indexing.index_article(article_ids[0]) == "indexed"
    monkeypatch.setattr(retrieval, "get_settings", lambda: settings)
    monkeypatch.setattr(retrieval, "embed", AsyncMock(return_value=[VECTOR]))
    monkeypatch.setattr(retrieval, "rerank", AsyncMock(return_value=None))
    async with factory() as db:
        nodes = await HybridRetriever(
            db, ["锂"], ["test-" + str(source_id)], category="price"
        ).aretrieve("supply bottleneck")
    assert len(nodes) == 1
    assert nodes[0].metadata["article_id"] == str(article_ids[0])
    assert nodes[0].text == BODY
    assert nodes[0].score == pytest.approx(1 / 61)


async def test_qdrant_stale_or_withdrawn_candidates_are_rechecked_in_sql(
    state, monkeypatch
):
    """Even published mirror payloads cannot override SQL review or revision."""
    import app.rag.indexer as indexing
    import app.rag.qdrant_store as mirror
    import app.rag.retriever as retrieval

    factory, source_id, _, _, article_ids = state
    collection = "miningintel_test_" + uuid4().hex
    settings = Settings(
        ML_ENABLED=True,
        QDRANT_URL="http://test.invalid",
        QDRANT_COLLECTION=collection,
    )
    monkeypatch.setattr(indexing, "SessionFactory", factory)
    monkeypatch.setattr(indexing, "get_settings", lambda: settings)
    monkeypatch.setattr(
        indexing,
        "embed",
        AsyncMock(side_effect=lambda texts, **_: [VECTOR] * len(texts)),
    )
    for article_id in article_ids[:2]:
        assert await indexing.index_article(article_id) == "indexed"
    client = (
        AsyncQdrantClient(url=os.environ["TEST_QDRANT_URL"])
        if os.getenv("TEST_QDRANT_URL")
        else AsyncQdrantClient(":memory:")
    )
    monkeypatch.setattr(mirror, "get_settings", lambda: settings)
    store = QdrantStore(client)
    try:
        await store.ensure_collections()
        async with factory.begin() as db:
            for article_id in article_ids[:2]:
                article = await db.get(Article, article_id)
                chunk = await db.scalar(
                    select(ArticleChunk).where(ArticleChunk.article_id == article_id)
                )
                await store.replace_article(
                    article_id,
                    VECTOR,
                    {
                        "article_id": str(article_id),
                        "revision": "obsolete-revision",
                        "embedding_model": settings.EMBEDDING_MODEL,
                        "status": "published",
                        "minerals": ["锂"],
                        "regions": ["test-" + str(source_id)],
                        "category": "price",
                    },
                    [
                        {
                            "id": str(chunk.id),
                            "vector": VECTOR,
                            "text": chunk.text,
                            "start_char": chunk.start_char,
                            "end_char": chunk.end_char,
                        }
                    ],
                )
                # Remove the SQL vector channel to test mirror hits in isolation.
                chunk.embedding = None
        monkeypatch.setattr(retrieval, "get_settings", lambda: settings)
        monkeypatch.setattr(retrieval, "embed", AsyncMock(return_value=[VECTOR]))
        monkeypatch.setattr(retrieval, "rerank", AsyncMock(return_value=None))
        monkeypatch.setattr(
            retrieval,
            "create_client",
            lambda: SimpleNamespace(
                query_points=client.query_points, close=AsyncMock()
            ),
        )
        hits = await store.search(
            VECTOR,
            minerals=["锂"],
            regions=["test-" + str(source_id)],
            category="price",
            start=None,
            end=None,
            limit=20,
        )
        assert len(hits) == 2
        async with factory() as db:
            assert not await HybridRetriever(
                db, ["锂"], ["test-" + str(source_id)], category="price"
            ).aretrieve("supply bottleneck")
        # An unpublished SQL article stays hidden even with a current mirror revision.
        async with factory.begin() as db:
            article = await db.get(Article, article_ids[0])
            article.status = "processed"
        from qdrant_client import models

        async with factory() as db:
            article = await db.get(Article, article_ids[0])
            await client.set_payload(
                store.chunks,
                {"revision": article.embedding_hash},
                models.Filter(
                    must=[
                        models.FieldCondition(
                            key="article_id",
                            match=models.MatchValue(value=str(article.id)),
                        )
                    ]
                ),
                wait=True,
            )
            assert not await HybridRetriever(
                db, ["锂"], ["test-" + str(source_id)], category="price"
            ).aretrieve("supply bottleneck")
    finally:
        if os.getenv("TEST_QDRANT_URL"):
            await client.delete_collection(store.chunks)
            await client.delete_collection(store.articles)
        await client.close()


async def test_chat_api_sse_history_followups_weather_and_ownership(state, monkeypatch):
    import app.main as main
    import app.rag.qa_chain as qa
    import app.rag.retriever as retrieval

    factory, source_id, user_id, other_id, _ = state
    monkeypatch.setattr(main, "limited", AsyncMock(return_value=False))
    monkeypatch.setattr(qa, "get_settings", lambda: Settings(LLM_API_KEY="test"))
    monkeypatch.setattr(retrieval, "embed", AsyncMock(return_value=[None]))
    monkeypatch.setattr(retrieval, "rerank", AsyncMock(return_value=None))
    monkeypatch.setattr(
        qa,
        "HybridRetriever",
        lambda db, minerals, regions, **filters: HybridRetriever(
            db, minerals, ["test-" + str(source_id)], **filters
        ),
    )

    async def generate(_, prompt):
        data = json.loads(prompt)
        evidence = next(item for item in data["evidence"] if item["quote"] == BODY)
        return {
            "claims": [
                {
                    "text": "测试资料显示锂矿报价涨到110 USD/t。",
                    "evidence": evidence["index"],
                    "quote": BODY,
                }
            ]
        }

    generation = AsyncMock(side_effect=generate)
    monkeypatch.setattr(qa, "complete_json", generation)

    async def override():
        async with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {create_token(user_id)}"},
    ) as client:
        response = await client.post(
            "/api/chat", json={"question": "2026年锂矿价格走势如何"}
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["mode"] == "grounded" and "[1]" in data["answer"]
        assert data["sources"][0]["snippet"] == BODY
        assert data["sources"][0]["source_name"] == "RAG 测试信源（虚构）"
        session_id = data["session_id"]
        for _ in range(5):
            followup = await client.post(
                "/api/chat",
                json={"question": "那为什么上涨呢？", "session_id": session_id},
            )
            assert followup.status_code == 200 and followup.json()["sources"]
        assert len(json.loads(generation.await_args.args[1])["history"]) == 5
        calls = generation.await_count
        weather = await client.post(
            "/api/chat", json={"question": "今天天气怎么样", "session_id": session_id}
        )
        assert (
            weather.json()["answer"] == qa.INSUFFICIENT
            and weather.json()["sources"] == []
        )
        assert generation.await_count == calls
        streamed = await client.post(
            "/api/chat/stream",
            json={"question": "2026年锂矿价格走势如何", "session_id": session_id},
        )
        assert (
            streamed.status_code == 200
            and "text/event-stream" in streamed.headers["content-type"]
        )
        assert streamed.text.index("event: sources") < streamed.text.index(
            "event: delta"
        )
        frames = [
            frame.split("\ndata: ", 1)
            for frame in streamed.text.split("\n\n")
            if "\ndata: " in frame
        ]
        complete = json.loads(
            next(data for event, data in frames if event == "event: done")
        )
        deltas = "".join(
            json.loads(data)["text"]
            for event, data in frames
            if event == "event: delta"
        )
        assert complete["answer"] == deltas
        history = await client.get(f"/api/chat/history/{session_id}")
        assert len(history.json()) == 8
        assert history.json()[-1]["id"] == complete["message_id"]
        other_headers = {"Authorization": f"Bearer {create_token(other_id)}"}
        assert (
            await client.get(f"/api/chat/history/{session_id}", headers=other_headers)
        ).status_code == 404
        assert (
            await client.delete(
                f"/api/chat/session/{session_id}", headers=other_headers
            )
        ).status_code == 404
        assert (
            await client.delete(f"/api/chat/session/{session_id}")
        ).status_code == 204
        assert (await client.get(f"/api/chat/history/{session_id}")).status_code == 404
    async with factory() as db:
        assert await db.get(ChatSession, session_id) is None
