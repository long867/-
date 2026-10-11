"""Semantic contracts, precise citations and actual local Qdrant filtering."""

import json
import os
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import numpy as np
import pytest
from llama_index.core.schema import NodeWithScore, TextNode
from qdrant_client import AsyncQdrantClient

from app.core.config import Settings
from app.models import Article
from app.rag.indexer import index_text, revision_hash
from app.rag.qa_chain import (
    INSUFFICIENT,
    Claim,
    GroundedAnswer,
    GroundedSynthesizer,
    contextual_query,
    reference_list,
    validate_claims,
)
from app.rag.qdrant_store import QdrantStore
from app.rag.retriever import HybridRetriever
from app.schemas.api import ChatInput, Citation


def source() -> Citation:
    return Citation(
        index=1,
        article_id=uuid4(),
        chunk_id=uuid4(),
        title="测试：锂价",
        url="https://example.com/fixture",
        quote="Lithium price rose from 100 to 110 USD/t.",
        start_char=50,
        end_char=92,
        published_at=datetime(2026, 1, 2, tzinfo=UTC),
        source_name="测试信源（虚构）",
    )


async def test_encoder_enforces_model_token_budget(monkeypatch) -> None:
    import app.rag.embedding as module

    calls = []

    class Encoder:
        def encode(self, texts, **kwargs):
            calls.append(kwargs)
            return {"dense_vecs": np.ones((len(texts), 1024))}

    monkeypatch.setattr(module, "get_settings", lambda: Settings(ML_ENABLED=True))
    monkeypatch.setattr(module, "embedding_model", lambda: Encoder())
    vectors = await module.embed(["锂 " * 10000, "铜"], max_tokens=512)
    assert calls == [{"batch_size": 8, "max_length": 512}]
    assert len(vectors) == 2 and all(len(vector) == 1024 for vector in vectors)


def test_chinese_index_readiness_and_revision() -> None:
    article = Article(
        id=uuid4(),
        title="Lithium",
        content="Original",
        language="en",
        category="news",
        status="published",
        minerals=["锂"],
        regions=[],
        url="https://example.com/fixture",
    )
    with pytest.raises(ValueError, match="Chinese"):
        index_text(article)
    article.title_zh, article.summary_zh, article.content_zh = "锂", "摘要", "中文正文"
    assert index_text(article) == "锂\n\n摘要\n\n中文正文"
    before = revision_hash(article, "信源")
    article.content_zh = "修正后的正文"
    assert revision_hash(article, "信源") != before
    assert revision_hash(article, "另一信源") != revision_hash(article, "信源")


def test_followups_preserve_topic_but_weather_does_not() -> None:
    history = [SimpleNamespace(question="2026年锂矿价格走势如何", mode="grounded")]
    query, filters = contextual_query(ChatInput(question="那为什么上涨呢？"), history)
    assert "锂矿" in query and filters["minerals"] == ["锂"]
    assert filters["start"] == datetime(2026, 1, 1, tzinfo=UTC)
    assert contextual_query(ChatInput(question="今天天气怎么样"), history) == ("", {})
    _, filters = contextual_query(ChatInput(question="那2027年呢？"), history)
    assert filters["start"].year == 2027
    query, filters = contextual_query(ChatInput(question="铜矿政策如何？"), history)
    assert "锂" not in query and filters["minerals"] == ["铜"]


def test_every_sentence_cited_and_fabricated_numbers_rejected() -> None:
    item = source()
    answer, citations = validate_claims(
        GroundedAnswer(
            claims=[
                Claim(
                    text="锂价上涨。报价达到110 USD/t。",
                    evidence=1,
                    quote=item.quote,
                )
            ]
        ),
        [item],
    )
    assert answer.count("[1]") == 2
    assert citations[0].snippet == item.quote and citations[0].id == 1
    with pytest.raises(ValueError, match="numerical"):
        validate_claims(
            GroundedAnswer(
                claims=[
                    Claim(
                        text="价格涨到999美元。",
                        evidence=1,
                        quote=item.quote,
                    )
                ]
            ),
            [item],
        )


@pytest.mark.parametrize("text", ["锂价为11 USD/t。", "锂价达到110米。"])
def test_claims_reject_numeric_substrings_and_unit_substitution(text) -> None:
    item = source()
    with pytest.raises(ValueError):
        validate_claims(
            GroundedAnswer(claims=[Claim(text=text, evidence=1, quote=item.quote)]),
            [item],
        )


def test_reference_date_preserves_the_shanghai_spot_quote_day() -> None:
    item = source().model_copy(
        update={"published_at": datetime(2026, 10, 8, 16, tzinfo=UTC)}
    )
    assert "2026-10-09" in reference_list([item])


async def test_empty_claims_produce_exact_insufficiency(monkeypatch) -> None:
    import app.rag.qa_chain as module

    item = source()
    node = NodeWithScore(
        node=TextNode(
            id_=str(item.chunk_id),
            text=item.quote,
            metadata={
                **item.model_dump(mode="json"),
                "article_id": str(item.article_id),
            },
        )
    )
    generation = AsyncMock(return_value={"claims": []})
    monkeypatch.setattr(module, "complete_json", generation)
    monkeypatch.setattr(module, "get_settings", lambda: Settings(LLM_API_KEY="test"))
    response = await GroundedSynthesizer("天气如何", []).asynthesize("weather", [node])
    assert str(response) == INSUFFICIENT and response.metadata["sources"] == []


async def test_generation_receives_only_latest_five_rounds(monkeypatch) -> None:
    import app.rag.qa_chain as module

    item = source()
    history = [
        SimpleNamespace(question=f"测试问题{i}", answer=f"测试答案{i}")
        for i in range(7)
    ]
    generation = AsyncMock(return_value={"claims": []})
    monkeypatch.setattr(module, "complete_json", generation)
    monkeypatch.setattr(module, "get_settings", lambda: Settings(LLM_API_KEY="test"))
    node = NodeWithScore(
        node=TextNode(
            id_=str(item.chunk_id),
            text=item.quote,
            metadata=item.model_dump(mode="json"),
        )
    )
    await GroundedSynthesizer("锂价", history).asynthesize("锂价", [node])
    prompt = json.loads(generation.await_args.args[1])
    assert len(prompt["history"]) == 5
    assert prompt["history"][0]["question"] == "测试问题2"


async def test_qdrant_filters_and_replacement_remove_stale_chunks() -> None:
    client = (
        AsyncQdrantClient(url=os.environ["TEST_QDRANT_URL"])
        if os.getenv("TEST_QDRANT_URL")
        else AsyncQdrantClient(":memory:")
    )
    store = QdrantStore(client)
    store.articles = "miningintel_test_" + uuid4().hex
    store.chunks = store.articles + "_chunks"
    vector = [1.0] + [0.0] * 1023
    article_id, chunk_id, replacement = uuid4(), uuid4(), uuid4()
    settings = Settings(_env_file=None)
    metadata = {
        "article_id": str(article_id),
        "status": "published",
        "revision": "v1",
        "embedding_model": settings.EMBEDDING_MODEL,
        "minerals": ["锂"],
        "regions": ["澳大利亚"],
        "category": "price",
        "published_ts": datetime(2026, 1, 2, tzinfo=UTC).timestamp(),
    }
    try:
        await store.ensure_collections()
        await store.replace_article(
            article_id,
            vector,
            metadata,
            [
                {
                    "id": str(chunk_id),
                    "vector": vector,
                    "text": "TEST FIXTURE",
                    "start_char": 0,
                    "end_char": 12,
                }
            ],
        )
        filters = {
            "minerals": ["锂"],
            "regions": ["澳大利亚"],
            "category": "price",
            "start": datetime(2026, 1, 1, tzinfo=UTC),
            "end": datetime(2027, 1, 1, tzinfo=UTC),
            "limit": 20,
        }
        assert await store.search(vector, **filters) == [(chunk_id, "v1")]
        assert await store.search(vector, **{**filters, "minerals": ["铜"]}) == []
        assert await store.search(vector, **{**filters, "category": "policy"}) == []
        assert await store.search(vector, **{**filters, "end": filters["start"]}) == []
        await store.replace_article(
            article_id,
            vector,
            {**metadata, "revision": "v2"},
            [
                {
                    "id": str(replacement),
                    "vector": vector,
                    "text": "UPDATED FIXTURE",
                    "start_char": 0,
                    "end_char": 15,
                }
            ],
        )
        assert await store.search(vector, **filters) == [(replacement, "v2")]
        assert (await client.count(store.articles)).count == 1
    finally:
        if os.getenv("TEST_QDRANT_URL"):
            await client.delete_collection(store.chunks)
            await client.delete_collection(store.articles)
        await client.close()


async def test_rerank_only_top_twenty_and_returns_reranker_scores(monkeypatch) -> None:
    import app.rag.retriever as module

    rows = [
        (
            SimpleNamespace(id=uuid4(), text=f"Copper {i}", start_char=0, end_char=9),
            SimpleNamespace(
                id=uuid4(),
                title="铜",
                title_zh="铜",
                url="https://example.com",
                minerals=["铜"],
                regions=[],
                category="news",
                published_at=None,
            ),
            "Test source",
        )
        for i in range(40)
    ]
    db = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(all=lambda: rows))
    )
    monkeypatch.setattr(module, "embed", AsyncMock(return_value=[None]))
    ranker = AsyncMock(return_value=[i / 20 for i in range(20)])
    monkeypatch.setattr(module, "rerank", ranker)
    monkeypatch.setattr(module, "get_settings", lambda: Settings(_env_file=None))
    nodes = await HybridRetriever(db, ["铜"]).aretrieve("铜矿")
    assert len(ranker.await_args.args[1]) == 20 and len(nodes) == 5
    assert nodes[0].score == 0.95 and nodes[0].metadata["source_name"] == "Test source"


@pytest.mark.parametrize(
    "dates",
    [
        {"start": "2026-01-01T00:00:00"},
        {"start": "2027-01-01T00:00:00Z", "end": "2026-01-01T00:00:00Z"},
    ],
)
def test_chat_rejects_ambiguous_or_reversed_dates(dates) -> None:
    with pytest.raises(ValueError):
        ChatInput(question="锂矿价格", **dates)
