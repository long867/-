"""Chinese answer delivery without sacrificing original evidence or quantities."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models import ChatMessage
from app.rag.localization import (
    chinese_excerpt_answer,
    chinese_prose,
    localize_citations,
    localized_history,
    translation_valid,
)
from app.schemas.api import Citation


def citation() -> Citation:
    return Citation(
        index=1,
        article_id=uuid4(),
        chunk_id=uuid4(),
        title="金价报道",
        url="https://example.com/gold",
        quote="Gold rose 3% to US$2,500/oz.",
        start_char=25,
        end_char=51,
        published_at=None,
        source_name="Official bulletin",
        summary_zh="报道披露黄金报价上涨，并保留原始报价的币种和计量单位。",
    )


def test_translation_preserves_currency_values_and_original_units():
    assert translation_valid(
        "Gold rose 3% to US$2,500/oz.", "金价上涨3%，至US$2,500/oz。"
    )
    assert not translation_valid("Gold rose 3%.", "金价上涨30%。")
    assert not translation_valid("Raised £1 million.", "筹集1百万欧元。")
    assert not translation_valid("Output was 10 tonnes.", "产量为10。")
    assert not chinese_prose(
        "中文：The gold price increased sharply this week on news."
    )


async def test_batch_translation_keeps_exact_original_offsets_and_caches(monkeypatch):
    import app.rag.localization as module

    cache = SimpleNamespace(
        get=AsyncMock(return_value=None), set=AsyncMock(), aclose=AsyncMock()
    )
    monkeypatch.setattr(module.Redis, "from_url", lambda *a, **kw: cache)
    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: Settings(LLM_API_KEY="fixture", CACHE_ENABLED=True, _env_file=None),
    )
    generate = AsyncMock(
        return_value={
            "items": [{"id": "excerpt-1", "quote_zh": "金价上涨3%，至US$2,500/oz。"}]
        }
    )
    monkeypatch.setattr(module, "complete_json", generate)
    original = citation()
    duplicate = original.model_copy(update={"index": 2})
    results = await localize_citations([original, duplicate])
    assert results[0].quote == original.quote == results[0].snippet
    assert (results[0].start_char, results[0].end_char) == (25, 51)
    assert results[0].quote_zh == results[1].quote_zh == "金价上涨3%，至US$2,500/oz。"
    assert original.quote_zh is None
    assert len(json.loads(generate.await_args.args[1])["excerpts"]) == 1
    cache.set.assert_awaited_once()
    cache.aclose.assert_awaited_once()
    assert original.quote not in chinese_excerpt_answer(results)


@pytest.mark.parametrize("failure", ["outage", "invented"])
async def test_failed_translation_uses_labeled_chinese_summary(monkeypatch, failure):
    import app.rag.localization as module

    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: Settings(LLM_API_KEY="fixture", CACHE_ENABLED=False, _env_file=None),
    )
    generate = AsyncMock(
        return_value={"items": [{"id": "excerpt-1", "quote_zh": "金价上涨30%。"}]}
    )
    if failure == "outage":
        generate.side_effect = TimeoutError("Fixture outage")
    monkeypatch.setattr(module, "complete_json", generate)
    original = citation()
    result = (await localize_citations([original]))[0]
    assert result.quote_zh is None
    assert result.quote == original.quote
    answer = chinese_excerpt_answer([result])
    assert "来源文章中文摘要" in answer and "[1]" in answer
    assert original.quote not in answer and "30%" not in answer


async def test_cached_translation_needs_no_model_and_rejects_stale_values(monkeypatch):
    import app.rag.localization as module

    cache = SimpleNamespace(
        get=AsyncMock(return_value="金价上涨3%，至US$2,500/oz。".encode()),
        aclose=AsyncMock(),
    )
    monkeypatch.setattr(module.Redis, "from_url", lambda *a, **kw: cache)
    monkeypatch.setattr(
        module, "get_settings", lambda: Settings(CACHE_ENABLED=True, _env_file=None)
    )
    generate = AsyncMock(side_effect=AssertionError("Cached history must not generate"))
    monkeypatch.setattr(module, "complete_json", generate)
    result = (await localize_citations([citation()], translate=False))[0]
    assert result.quote_zh
    generate.assert_not_awaited()
    cache.get.return_value = "金价上涨30%，至US$2,500/oz。".encode()
    result = (await localize_citations([citation()], translate=False))[0]
    assert result.quote_zh is None


async def test_legacy_history_is_chinese_without_mutating_stored_original(monkeypatch):
    import app.rag.localization as module

    monkeypatch.setattr(
        module, "get_settings", lambda: Settings(CACHE_ENABLED=False, _env_file=None)
    )
    original = citation().model_copy(update={"summary_zh": None})
    message = ChatMessage(
        id=uuid4(),
        session_id=uuid4(),
        question="金价走势？",
        answer="已找到以下原文证据：" + original.quote,
        mode="extractive",
        sources_json=[original.model_dump(mode="json")],
    )
    from datetime import UTC, datetime

    message.created_at = datetime.now(UTC)
    article = SimpleNamespace(
        id=original.article_id,
        title_zh="黄金市场动态",
        summary_zh="该报道提供了黄金价格变化的相关信息，可通过来源查看具体报价。",
    )
    db = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [article]))
    )
    view = (await localized_history(db, [message]))[0]
    assert original.quote not in view.answer and "来源文章中文摘要" in view.answer
    assert "黄金市场动态" in view.answer
    assert view.sources_json[0]["quote"] == original.quote
    assert view.sources_json[0]["snippet"] == original.quote
    assert original.quote in message.answer
    assert message.sources_json[0]["summary_zh"] is None
