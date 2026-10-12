"""Grounding, publication visibility, sparse evidence and owned research archives."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from test_business_api import business as business

from app.schemas.research import (
    ResearchCoverage,
    ResearchGeneration,
    ResearchInput,
    ResearchSnapshot,
    ResearchSource,
)
from app.services.research_service import evidence_based_research, validate_generation
from pipeline.processors.policy_document import general_mineral_policy
from pipeline.processors.translator import summary_measurements_valid
from pipeline.schemas import SourceDefinition


def snapshot():
    """Keep original evidence available for exact quotation validation."""
    return ResearchSnapshot(
        scope=ResearchInput(),
        generated_at=datetime.now(UTC),
        coverage=ResearchCoverage(article_count=1, evidence_count=1, source_count=1),
        limitations=[],
        sources=[
            ResearchSource(
                index=1,
                article_id=uuid4(),
                title="加拿大锂产量增长10%",
                original_title="Lithium output increased by 10% in Canada",
                original_excerpt="Lithium output increased by 10% in Canada.",
                original_hash="test",
                snippet="加拿大锂产量增长。",
                source_name="加拿大政府",
                url="https://www.canada.ca/example",
                category="policy",
                authority_score=10,
                published_at=datetime.now(UTC),
            )
        ],
    )


def test_grounded_facts_offsets_and_independent_publisher_confidence():
    evidence = snapshot()
    baseline = evidence_based_research(evidence)
    baseline.scenarios[0].confidence = "medium"
    validated = validate_generation(
        ResearchGeneration.model_validate(baseline.model_dump()), evidence
    )
    assert validated.facts[0].quote == evidence.sources[0].original_title
    assert validated.facts[0].end_char == len(validated.facts[0].quote)
    assert validated.scenarios[0].confidence == "low"


@pytest.mark.parametrize(
    "change",
    ["fabricated_quote", "wrong_number", "wrong_source", "forecast", "guarantee"],
)
def test_research_rejects_unsupported_facts_and_forecasts(change):
    evidence = snapshot()
    generation = ResearchGeneration.model_validate(
        evidence_based_research(evidence).model_dump()
    )
    if change == "fabricated_quote":
        generation.facts[0].quote = "Unrelated invented quote"
    elif change == "wrong_number":
        generation.facts[0].text = "加拿大锂产量增长20%"
    elif change == "wrong_source":
        generation.actions[0].source_ids = [99]
    elif change == "forecast":
        generation.scenarios[0].impact = "锂价格可能上涨30%，应立即采取措施。"
    else:
        generation.scenarios[0].impact = "该政策一定会推动锂价格上涨，可以保证收益。"
    with pytest.raises(ValueError):
        validate_generation(generation, evidence)


def test_no_evidence_has_no_invented_actions_and_policy_whitelist_is_bounded():
    evidence = snapshot().model_copy(update={"sources": []})
    result = evidence_based_research(evidence)
    assert result.mode == "insufficient" and not result.scenarios and not result.actions
    source = SourceDefinition(
        name="政府文件",
        url="https://www.gov.cn/law",
        type="web",
        category="policy",
        authority_score=10,
        parser_config={"document_kind": "regulation", "mineral_scope_all": True},
    )
    assert general_mineral_policy(source, "矿产资源法", "矿产资源开发与保护")
    assert not general_mineral_policy(
        source.model_copy(update={"url": "https://gov.cn.example.org/law"}),
        "矿产资源法",
        "矿产资源开发与保护",
    )
    assert not summary_measurements_valid(
        "US$55 million investment", "投资US$55 million亿美元"
    )


def test_grounded_proper_name_watch_items_get_chinese_context():
    evidence = snapshot()
    evidence.sources[0].original_excerpt += " CleanTech Lithium announced an update."
    generation = ResearchGeneration.model_validate(
        evidence_based_research(evidence).model_dump()
    )
    generation.watchlist = ["CleanTech Lithium"]
    result = validate_generation(generation, evidence)
    assert result.watchlist == ["持续核对CleanTech Lithium的后续公开资料"]
    generation.watchlist = ["Invented Company"]
    with pytest.raises(ValueError):
        validate_generation(generation, evidence)


@pytest.mark.integration
async def test_research_api_real_scopes_owned_history_and_changed_evidence(business):
    from app.models import Article

    client = business["client"]
    response = await client.get(
        "/api/research/overview", params={"region": business["region"]}
    )
    assert response.status_code == 200
    result = response.json()
    assert result["coverage"]["article_count"] == 3
    assert len(result["sources"]) == 3 and result["mode"] == "evidence_based"
    assert result["scenarios"] and result["actions"]
    assert business["ids"][3].hex not in str(result)
    response = await client.post(
        "/api/research", json={"region": business["region"], "focus": "矿产供应链影响"}
    )
    assert response.status_code == 401
    response = await client.post(
        "/api/research",
        json={"region": business["region"], "focus": "矿产供应链影响"},
        headers=business["headers"],
    )
    assert response.status_code == 200
    report = response.json()
    report_id = report["id"]
    assert (
        await client.get(
            f"/api/research/reports/{report_id}", headers=business["headers"]
        )
    ).status_code == 200
    assert (
        await client.get(
            f"/api/research/reports/{report_id}", headers=business["other_headers"]
        )
    ).status_code == 404
    history = (
        await client.get("/api/research/history", headers=business["headers"])
    ).json()
    assert history[0]["id"] == report_id
    async with business["factory"].begin() as db:
        article = await db.get(Article, business["ids"][0])
        article.content = (
            "Changed original evidence after the research report was saved."
        )
    assert (
        await client.get(
            f"/api/research/reports/{report_id}", headers=business["headers"]
        )
    ).status_code == 409


@pytest.mark.integration
async def test_latest_digest_uses_real_calendar_period_and_charts(business):
    client = business["client"]
    response = await client.get("/api/digest/daily", params={"scope": "latest"})
    assert response.status_code == 200
    result = response.json()
    assert result["stats"]["article_count"] > 0 and result["sources"]
    assert result["analysis"]["coverage_by_day"] and result["analysis"]["hot_minerals"]
    policy = (
        await client.get(
            "/api/policies",
            params={
                "region": business["region"],
                "date_basis": "published_at",
                "date_to": datetime.now(UTC).date().isoformat(),
            },
        )
    ).json()
    assert policy["total"] == 1 and policy["items"][0]["published_at"]
