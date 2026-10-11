"""Calendar boundaries and grounding gates for generated briefs."""

from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.schemas.intelligence import DigestOut, DigestSource, DigestStats
from app.services.digest_service import period_bounds


def test_calendar_periods_use_shanghai_midnight_and_exclusive_end():
    now = datetime(2026, 12, 31, 17, tzinfo=UTC)
    start, end = period_bounds("daily", now)
    assert start.date() == date(2027, 1, 1) and end.date() == date(2027, 1, 2)
    assert start.utcoffset().total_seconds() == 28800
    start, end = period_bounds("monthly", datetime(2026, 12, 25, tzinfo=UTC))
    assert start.date() == date(2026, 12, 1) and end.date() == date(2027, 1, 1)
    start, end = period_bounds("weekly", datetime(2026, 10, 11, tzinfo=UTC))
    assert start.date() == date(2026, 10, 5) and (end - start).days == 7


@pytest.mark.parametrize(
    "claim",
    [
        {
            "text": "铜矿产量增长99%。",
            "evidence": 1,
            "quote": "铜矿产量增长10%，公司披露生产数据。",
        },
        {
            "text": "铜矿产量增长10%。",
            "evidence": 2,
            "quote": "铜矿产量增长10%，公司披露生产数据。",
        },
        {
            "text": "铜矿产量增长10%。",
            "evidence": 1,
            "quote": "不存在于原文的证据片段。",
        },
        {
            "text": "铜矿产量增长10吨。",
            "evidence": 1,
            "quote": "铜矿产量增长10%，公司披露生产数据。",
        },
    ],
)
async def test_digest_rejects_invented_numbers_unknown_citations_and_false_quotes(
    monkeypatch, claim
):
    import app.services.digest_service as module

    @asynccontextmanager
    async def session():
        yield None

    snapshot = DigestOut(
        kind="weekly",
        period_start=date(2026, 10, 5),
        period_end=date(2026, 10, 12),
        timezone="Asia/Shanghai",
        title="测试周报",
        content="原文摘录",
        mode="extractive",
        generated_at=datetime.now(UTC),
        stats=DigestStats(
            article_count=1,
            source_count=1,
            minerals={"铜": 1},
            regions={},
            categories={"news": 1},
        ),
        sources=[
            DigestSource(
                article_id=uuid4(),
                title="铜矿报告",
                url="https://example.com/report",
                source_name="TEST FIXTURE",
                published_at=datetime.now(UTC),
                snippet="铜矿产量增长10%，公司披露生产数据。",
            )
        ],
    )
    monkeypatch.setattr(module, "SessionFactory", session)
    monkeypatch.setattr(module, "get_digest", AsyncMock(return_value=snapshot))
    monkeypatch.setattr(
        module, "get_settings", lambda: Settings(LLM_API_KEY="fixture", _env_file=None)
    )
    monkeypatch.setattr(
        module, "complete_json", AsyncMock(return_value={"claims": [claim]})
    )
    with pytest.raises(ValueError):
        await module.generate_digest("weekly")
