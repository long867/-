"""Consultation generation, fallback and evidence persistence behavior."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from llama_index.core.retrievers import BaseRetriever
from llama_index.core.schema import NodeWithScore, TextNode

from app.core.config import Settings
from app.rag.qa import answer_question
from app.schemas.api import ChatInput


@pytest.mark.parametrize("scenario", ["valid", "invented", "outage", "empty"])
async def test_qa_persists_only_verified_generation(scenario, monkeypatch) -> None:
    import app.rag.qa_chain as module

    chunk_id, article_id = uuid4(), uuid4()
    original = "Copper exports require permits according to the official policy."
    evidence = {
        str(chunk_id): (
            SimpleNamespace(
                id=chunk_id, text=original, start_char=20, end_char=20 + len(original)
            ),
            SimpleNamespace(
                id=article_id,
                title="Copper policy",
                title_zh=None,
                url="https://example.com/policy",
                published_at=None,
            ),
        )
    }

    class FixtureRetriever(BaseRetriever):
        def __init__(self, *_, **kwargs):
            super().__init__()
            self.evidence = evidence

        def _retrieve(self, query):
            raise RuntimeError("Use async")

        async def _aretrieve(self, query_bundle):
            if scenario == "empty":
                return []
            return [
                NodeWithScore(
                    node=TextNode(
                        id_=str(chunk_id),
                        text=original,
                        metadata={
                            "article_id": str(article_id),
                            "title": "Copper policy",
                            "url": "https://example.com/policy",
                            "published_at": None,
                            "source_name": "Official policy",
                            "start_char": 20,
                            "end_char": 20 + len(original),
                        },
                    ),
                    score=1,
                )
            ]

    monkeypatch.setattr(module, "HybridRetriever", FixtureRetriever)
    monkeypatch.setattr(
        module, "get_settings", lambda: Settings(LLM_API_KEY="fixture", _env_file=None)
    )
    generation = AsyncMock(
        return_value={
            "claims": [
                {
                    "text": "铜出口需要许可。",
                    "evidence": 1,
                    "quote": original
                    if scenario == "valid"
                    else "This quote was fabricated.",
                }
            ]
        }
    )
    if scenario == "outage":
        generation.side_effect = TimeoutError("fixture model outage")
    monkeypatch.setattr(module, "complete_json", generation)
    saved = []

    def add(item):
        item.id = uuid4()
        saved.append(item)

    db = SimpleNamespace(
        add=add,
        flush=AsyncMock(),
        execute=AsyncMock(),
        scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: [])),
    )
    result = await answer_question(
        db, uuid4(), ChatInput(question="铜出口需要许可吗？")
    )
    expected = {
        "valid": "grounded",
        "invented": "extractive",
        "outage": "extractive",
        "empty": "insufficient",
    }[scenario]
    assert result.mode == expected
    assert saved[-1].mode == expected
    assert saved[-1].sources_json == [
        item.model_dump(mode="json") for item in result.sources
    ]
    if scenario in {"invented", "outage"}:
        assert original in result.answer
        assert "fabricated" not in result.answer
    if scenario == "empty":
        assert not result.sources
        generation.assert_not_awaited()
