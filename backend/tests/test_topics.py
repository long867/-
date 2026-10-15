"""Rule fallback, model grounding, ownership and durable topic favorites."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from test_business_api import business as business

from app.core.config import get_settings
from app.schemas.topics import DraftTopic
from app.services import topic_service as service


def evidence(kind="article"):
    """Synthetic records belong exclusively to tests, never live initialization."""
    return service.Evidence(
        article_id=uuid4(),
        entity_id=uuid4(),
        evidence_type=kind,
        title="Copper tailings recovery study",
        title_zh="铜尾矿回收研究",
        content="Copper tailings were studied using flotation experiments.",
        url="https://example.com/TEST-TOPIC-FIXTURE",
        source_name="TEST FIXTURE",
        published_at=datetime.now(UTC),
        minerals=["铜"],
        regions=["测试地区"],
        keywords=["回收与循环利用"] if kind == "article" else ["环保"],
        authority=8,
        category="report" if kind == "article" else "policy",
    )


def draft(candidate):
    return {
        "key": candidate.key,
        "title": "铜尾矿回收技术的适用条件比较研究",
        "rationale": [
            {
                "evidence_index": 1,
                "quote_field": "title",
                "quote": candidate.evidence[0].title,
                "support": "可围绕原文开展回收方法比较与验证方案设计",
            }
        ],
    }


def test_rules_have_two_orientations_exact_original_quotes_and_real_scores():
    records = [evidence(), evidence("policy")]
    pool = service.candidates(records, {"铜": 40})
    assert {c.type for c in pool} == {"achievement", "social_science"}
    for candidate in pool:
        output = service.rule_proposal(candidate)
        assert output.mode == "rule" and output.references
        assert "待验证" in output.rationale and "[1]" in output.rationale
        assert output.references[0][2] == candidate.evidence[0].title
        assert 0 <= candidate.heat_score <= 100
    assert service.candidates([], {}) == []


def test_postgresql_window_constraint_quotes_reserved_identifier():
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.schema import CreateTable

    from app.models import Topic

    ddl = str(CreateTable(Topic.__table__).compile(dialect=postgresql.dialect()))
    assert 'CHECK ("window" IN' in ddl


async def test_no_model_configuration_never_calls_gateway(monkeypatch):
    gateway = AsyncMock(side_effect=AssertionError("must not call model"))
    monkeypatch.setattr(service, "complete_json", gateway)
    pool = service.candidates([evidence()], {})
    output = await service.proposals(pool, use_llm=True)
    assert all(p.mode == "rule" for p in output.values())
    gateway.assert_not_called()


@pytest.mark.parametrize(
    "response",
    [
        RuntimeError("gateway down"),
        {"topics": "wrong schema"},
        {"topics": [{"key": "unknown", "title": "未知主题测试", "rationale": []}]},
    ],
)
async def test_gateway_and_schema_failures_fall_back_without_fabricating(
    monkeypatch, response
):
    monkeypatch.setenv("LLM_API_KEY", "test-only")
    get_settings.cache_clear()
    mock = (
        AsyncMock(side_effect=response)
        if isinstance(response, Exception)
        else AsyncMock(return_value=response)
    )
    monkeypatch.setattr(service, "complete_json", mock)
    pool = service.candidates([evidence()], {})
    output = await service.proposals(pool, use_llm=True)
    assert output[pool[0].key].mode == "rule"
    assert output[pool[0].key].references[0][0].url == pool[0].evidence[0].url
    assert set(mock.call_args.kwargs) == {"system", "prompt"}


def test_false_citation_is_removed_with_its_reason_and_numbers_renumbered():
    candidate = service.candidates([evidence()], {})[0]
    payload = draft(candidate)
    payload["rationale"].insert(
        0,
        {
            "evidence_index": 99,
            "quote_field": "title",
            "quote": "Fabricated nonexistent research paper",
            "support": "可基于不存在的资料编造全新的研究方案",
        },
    )
    output = service.validate_draft(DraftTopic.model_validate(payload), candidate)
    assert output.mode == "llm" and len(output.references) == 1
    assert "不存在" not in output.rationale and "[99]" not in output.rationale
    assert "[1]" in output.rationale and "[2]" not in output.rationale


@pytest.mark.parametrize("mutation", ["quote", "number", "guarantee", "fact", "key"])
def test_invalid_model_reasons_and_forecasts_are_not_published(mutation):
    candidate = service.candidates([evidence()], {})[0]
    payload = draft(candidate)
    if mutation == "quote":
        payload["rationale"][0]["quote"] = "This invented quotation is absent"
    elif mutation == "number":
        payload["rationale"][0]["support"] = "可将铜回收率提升到99%，直接开展产业化"
    elif mutation == "guarantee":
        payload["title"] = "铜尾矿回收首次突破且保证成功研究"
    elif mutation == "fact":
        payload["rationale"][0]["support"] = "研究证明铜尾矿回收技术已经实现完全产业化"
    else:
        payload["key"] = "unknown"
    with pytest.raises(ValueError):
        service.validate_draft(DraftTopic.model_validate(payload), candidate)


async def test_good_model_returns_literal_content_span(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-only")
    get_settings.cache_clear()
    pool = service.candidates([evidence()], {})
    data = draft(pool[0])
    data["rationale"][0].update(
        quote_field="content", quote="using flotation experiments"
    )
    monkeypatch.setattr(
        service, "complete_json", AsyncMock(return_value={"topics": [data]})
    )
    result = (await service.proposals(pool, True))[pool[0].key]
    e, field, quote, offset, _ = result.references[0]
    assert result.mode == "llm" and field == "content"
    assert e.content[offset : offset + len(quote)] == quote


async def test_topic_routes_require_login_before_any_service(monkeypatch):
    from fastapi import FastAPI

    from app.api.topics import router
    from app.core.db import get_db

    app = FastAPI()
    app.include_router(router)

    async def no_db():
        yield object()

    monkeypatch.setattr(
        "app.api.topics.list_topics",
        AsyncMock(side_effect=AssertionError("must not run")),
    )
    app.dependency_overrides[get_db] = no_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            topic_id = uuid4()
            for method, path, body in [
                ("GET", "/api/v1/topics/recommendations", None),
                ("GET", f"/api/v1/topics/{topic_id}", None),
                ("POST", "/api/v1/topics/recommendations/refresh", {}),
                ("PUT", f"/api/v1/topics/{topic_id}/bookmark", None),
                ("DELETE", f"/api/v1/topics/{topic_id}/bookmark", None),
            ]:
                response = await client.request(method, path, json=body)
                assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.integration
async def test_real_topics_ownership_bookmark_refresh_and_withdrawal(business):
    from sqlalchemy import func, select

    from app.models import Article, Topic, TopicBookmark

    client, headers = business["client"], business["headers"]
    response = await client.get("/api/v1/topics/recommendations", headers=headers)
    assert response.status_code == 200 and response.json()["items"]
    assert response.headers["Cache-Control"] == "private, no-store"
    first = response.json()["items"][0]
    topic_id = first["id"]
    assert first["mode"] == "rule" and first["evidence_count"] > 0
    for e in first["evidence"]:
        assert e["article_id"] != str(business["ids"][3])
        assert e["source_url"].startswith(business["root"])
    base = f"/api/v1/topics/{topic_id}"
    assert (
        await client.get(base, headers=business["other_headers"])
    ).status_code == 404
    assert (
        await client.put(base + "/bookmark", headers=business["other_headers"])
    ).status_code == 404
    for _ in range(2):
        assert (
            await client.put(base + "/bookmark", headers=headers)
        ).status_code == 204
    detail = (await client.get(base, headers=headers)).json()
    assert detail["bookmarked"] is True
    async with business["factory"]() as db:
        assert (
            await db.scalar(
                select(func.count())
                .select_from(TopicBookmark)
                .where(TopicBookmark.topic_id == topic_id)
            )
            == 1
        )
        count = await db.scalar(
            select(func.count())
            .select_from(Topic)
            .where(Topic.user_id == business["user_id"])
        )
    await client.get("/api/v1/topics/recommendations", headers=headers)
    async with business["factory"]() as db:
        assert (
            await db.scalar(
                select(func.count())
                .select_from(Topic)
                .where(Topic.user_id == business["user_id"])
            )
            == count
        )
    saved = (
        await client.get(
            "/api/v1/topics/recommendations?bookmarked=true", headers=headers
        )
    ).json()
    assert saved["total"] == 1
    refreshed = await client.post(
        "/api/v1/topics/recommendations/refresh", headers=headers, json={}
    )
    assert refreshed.status_code == 200 and refreshed.json()["mode"] == "rule"
    assert (await client.get(base, headers=headers)).json()["bookmarked"] is True
    assert (
        await client.post(
            "/api/v1/topics/recommendations/refresh", headers=headers, json={}
        )
    ).status_code == 429
    for _ in range(2):
        assert (
            await client.delete(base + "/bookmark", headers=headers)
        ).status_code == 204
    assert (
        await client.get("/api/v1/topics/recommendations?window=bad", headers=headers)
    ).status_code == 422
    async with business["factory"].begin() as db:
        article = await db.get(Article, UUID(detail["evidence"][0]["article_id"]))
        article.status = "processed"
    assert (await client.get(base, headers=headers)).status_code == 404


@pytest.mark.integration
async def test_empty_or_future_corpus_returns_insufficient_and_no_topics(business):
    from app.models import Article

    async with business["factory"].begin() as db:
        for article_id in business["ids"]:
            row = await db.get(Article, article_id)
            row.published_at = datetime.now(UTC) + timedelta(days=1)
    result = await business["client"].get(
        "/api/v1/topics/recommendations", headers=business["headers"]
    )
    assert result.status_code == 200
    assert result.json()["items"] == [] and result.json()["mode"] == "insufficient"
    async with business["factory"].begin() as db:
        for article_id in business["ids"]:
            row = await db.get(Article, article_id)
            row.published_at = datetime.now(UTC) - timedelta(days=1)
            row.raw_json = {"date_precision": "month"}
    # A month-only date must not be presented as an exact publication day.
    result = await business["client"].get(
        "/api/v1/topics/recommendations", headers=business["headers"]
    )
    assert result.status_code == 200
    assert result.json()["items"] == [] and result.json()["mode"] == "insufficient"
