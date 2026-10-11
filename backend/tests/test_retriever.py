"""LlamaIndex integration, SQL filters and source-diversity behavior."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from app.core.config import Settings
from app.rag.retriever import HybridRetriever
from sqlalchemy.dialects import postgresql


async def test_llamaindex_retrieval_keeps_filters_and_source_diversity(
    monkeypatch,
) -> None:
    import app.rag.retriever as module

    article_ids = [uuid4() for _ in range(4)]
    rows = []
    for index in range(8):
        article_id = article_ids[0] if index < 4 else article_ids[index - 4]
        rows.append(
            (
                SimpleNamespace(
                    id=uuid4(),
                    text=f"Copper evidence {index}",
                    start_char=0,
                    end_char=20,
                ),
                SimpleNamespace(
                    id=article_id,
                    title="Copper policy",
                    title_zh=None,
                    published_at=None,
                    minerals=["铜"],
                    regions=["智利"],
                    category="policy",
                    url="https://example.com/policy",
                ),
                "Official policy",
            )
        )
    db = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(all=lambda: rows))
    )
    monkeypatch.setattr(
        module, "get_settings", lambda: Settings(ML_ENABLED=False, _env_file=None)
    )
    monkeypatch.setattr(module, "embed", AsyncMock(return_value=[None]))
    monkeypatch.setattr(module, "rerank", AsyncMock(return_value=None))
    retriever = HybridRetriever(db, ["铜"], ["智利"])
    nodes = await retriever.aretrieve("智利铜矿")
    first_source = [
        node
        for node in nodes
        if retriever.evidence[node.node.node_id][1].id == article_ids[0]
    ]
    assert len(first_source) == 2
    assert len(nodes) == 5
    statement = db.execute.await_args.args[0]
    compiled = str(
        statement.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )
    assert "articles.status = 'published'" in compiled
    assert "articles.minerals &&" in compiled
    assert "articles.regions &&" in compiled
    assert "ts_rank_cd" in compiled


async def test_no_candidates_returns_empty_nodes(monkeypatch) -> None:
    import app.rag.retriever as module

    db = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(all=lambda: []))
    )
    monkeypatch.setattr(module, "embed", AsyncMock(return_value=[None]))
    monkeypatch.setattr(module, "rerank", AsyncMock(return_value=None))
    retriever = HybridRetriever(db, [], [])
    assert await retriever.aretrieve("没有证据的问题") == []
