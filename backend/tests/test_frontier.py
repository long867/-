"""Scholarly provenance, precision, Chinese evidence checks and public visibility."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import httpx
import pytest
from test_business_api import business as business

from pipeline.fetchers.scholarly_fetcher import ScholarlyFetcher, publication
from pipeline.fetchers.transport import FetchTransport
from pipeline.processors.academic import validate_academic
from pipeline.schemas import SourceDefinition


def source() -> SourceDefinition:
    """Use the real supported endpoint and synthetic metadata only in tests."""
    return SourceDefinition(
        name="SCHOLARLY TEST FIXTURE",
        url="https://api.crossref.org/journals/2075-163X/works",
        type="api",
        category="report",
        authority_score=8,
        parser_config={
            "adapter": "crossref_journal",
            "direction": "exploration",
            "max_items": 8,
        },
    )


def record() -> dict:
    now = datetime.now(UTC)
    return {
        "DOI": "10.5555/COPPER-TEST",
        "type": "journal-article",
        "title": ["Copper tailings flotation recovery improves by 20%"],
        "abstract": (
            "<jats:p>Recovery improves by 20% in copper tailings experiments.</jats:p>"
        ),
        "container-title": ["TEST JOURNAL"],
        "publisher": "TEST PUBLISHER",
        "published-online": {"date-parts": [[now.year, now.month, now.day]]},
        "author": [
            {
                "given": "Ada",
                "family": "Example",
                "affiliation": [{"name": "Test Institute"}],
            }
        ],
    }


def test_month_and_year_dates_are_not_presented_as_invented_exact_days():
    stamp, label, precision = publication({"published": {"date-parts": [[2026, 9]]}})
    assert stamp.month == 9 and label == "2026-09" and precision == "month"
    assert publication({"issued": {"date-parts": [[2025]]}})[1:] == ("2025", "year")
    assert publication({"published": {"date-parts": [[2026, 13, 5]]}})[0] is None
    assert publication({"deposited": {"date-time": "2026-10-14"}})[0] is None


async def test_scholarly_doi_deduplication_real_dates_and_abstract_scope(monkeypatch):
    row = record()
    duplicate = deepcopy(row)
    duplicate["DOI"] = duplicate["DOI"].lower()
    future = deepcopy(row)
    future["DOI"] += "-FUTURE"
    later = datetime.now(UTC) + timedelta(days=10)
    future["published-online"] = {"date-parts": [[later.year, later.month, later.day]]}
    title_only = deepcopy(row)
    title_only["DOI"] += "-TITLE"
    title_only.pop("abstract")
    withdrawn = deepcopy(row)
    withdrawn["DOI"] += "-RETRACTED"
    withdrawn["update-to"] = [{"type": "retraction"}]
    response = httpx.Response(
        200,
        json={"message": {"items": [row, duplicate, future, title_only, withdrawn]}},
        request=httpx.Request("GET", source().url),
    )
    get = AsyncMock(return_value=response)
    monkeypatch.setattr(FetchTransport, "get", get)
    papers = await ScholarlyFetcher(source()).fetch()
    assert len(papers) == 2
    assert papers[0].url == "https://doi.org/10.5555/copper-test"
    assert "<jats" not in papers[0].content
    assert papers[0].raw_json["authors"] == ["Ada Example"]
    assert papers[0].raw_json["institutions"] == ["Test Institute"]
    assert "processing" in papers[0].raw_json["research_directions"]
    assert papers[1].raw_json["evidence_scope"] == "bibliographic"
    assert papers[1].content == papers[1].title
    assert "until-pub-date" in get.call_args.args[0]


def test_unsupported_hosts_cannot_enter_academic_processing():
    from pipeline.fetchers.scholarly_fetcher import scholarly_source

    assert scholarly_source(source())
    assert not scholarly_source(
        source().model_copy(
            update={
                "url": "https://api.crossref.org.example.net/journals/2075-163X/works"
            }
        )
    )


def test_title_only_records_cannot_acquire_invented_research_results():
    result = validate_academic(
        "Copper flotation",
        "Copper flotation",
        "en",
        {
            "title_zh": "铜浮选研究",
            "summary_zh": "研究证明回收率达到99%并已实现产业化。",
        },
        {},
        has_abstract=False,
    )
    assert "99%" not in result["summary_zh"] and "暂未提供摘要" in result["summary_zh"]
    with pytest.raises(ValueError, match="numeric"):
        validate_academic(
            "Recovery improves by 20%",
            "Recovery improves by 20%",
            "en",
            {"title_zh": "回收率提高30%"},
            {},
            has_abstract=False,
        )


def test_chemical_title_terms_must_not_be_mistranslated():
    from pipeline.processors.academic import check_title_terms

    check_title_terms("Co-Ni and Cu deposits", "钴-镍与铜矿床")
    with pytest.raises(ValueError, match="chemical"):
        check_title_terms("Co-Ni and Cu deposits", "共镍与铜矿床")


@pytest.mark.parametrize(
    "original,wrong,correct",
    [
        ("Molybdenite and talc flotation", "黄铜矿与滑石浮选", "辉钼矿与滑石浮选"),
        ("Flow field in a tundish", "钢包内流场研究", "中间包内流场研究"),
        (
            "Peridynamic rock fracture model",
            "周期动态岩石断裂模型",
            "近场动力学岩石断裂模型",
        ),
        (
            "Pegmatite in Altyn Tagh, NW China",
            "阿尔泰山东部伟晶岩",
            "中国西北阿尔金山伟晶岩",
        ),
    ],
)
def test_scientific_mineral_equipment_method_and_place_terms(original, wrong, correct):
    from pipeline.processors.academic import check_title_terms

    with pytest.raises(ValueError):
        check_title_terms(original, wrong)
    check_title_terms(original, correct)


def test_abstract_summary_rejects_invented_measurements():
    with pytest.raises(ValueError, match="invented"):
        validate_academic(
            "Copper flotation",
            "Copper recovery improved by 20% in experiments.",
            "en",
            {
                "title_zh": "铜浮选研究",
                "summary_zh": (
                    "研究围绕铜尾矿的浮选回收开展实验，比较不同处理条件下的回收表现，"
                    "并在原有工艺基础上考察试验变化。研究给出的回收率提升为50%，"
                    "具体试验条件和适用范围仍应查看原始论文。"
                ),
            },
            {},
            has_abstract=True,
        )


def test_overlong_translation_keeps_complete_method_and_result_sentences():
    from pipeline.processors.academic import concise_digest

    start = "该研究考察铜尾矿超声预处理对浮选回收的影响。"
    middle = "研究团队对矿物的表面形貌和不同工艺条件进行了系统比较。" * 12
    result = "最佳实验条件下，铜回收率为80%，该结果限于论文所述实验。"
    summary = concise_digest(start + middle + result)
    assert summary.startswith(start) and result in summary
    assert len(summary) <= 260 and summary.endswith("。")


@pytest.mark.integration
async def test_public_frontier_filters_pagination_precision_and_hidden_records(
    business,
):
    from app.core.cache import invalidate_public_cache
    from app.models import Article, Source

    async with business["factory"].begin() as db:
        paper = await db.get(Article, business["ids"][0])
        journal = await db.get(Source, paper.source_id)
        journal.config_json = {
            "adapter": "crossref_journal",
            "headers": {"secret": "NEVER EXPOSE"},
        }
        for index, paper_id in enumerate(business["ids"]):
            item = await db.get(Article, paper_id)
            item.category = "report"
            item.raw_json = {
                "document_kind": "research_paper",
                "doi": f"10.5555/frontier-{index}",
                "journal": "TEST JOURNAL",
                "authors": ["Ada Example"],
                "research_directions": ["processing" if index == 0 else "governance"],
                "abstract_available": index == 0,
                "published_date": "2026-09",
                "date_precision": "month",
            }
        future = await db.get(Article, business["ids"][2])
        future.published_at = datetime.now(UTC) + timedelta(days=3)
    await invalidate_public_cache()
    client = business["client"]
    page = await client.get("/api/frontier?page_size=1&direction=processing")
    assert page.status_code == 200
    data = page.json()
    assert data["total"] == 1 and len(data["items"]) == 1
    assert data["items"][0]["date_precision"] == "month"
    assert data["items"][0]["published_date"] == "2026-09"
    assert "NEVER EXPOSE" not in page.text
    searched = await client.get(
        "/api/frontier?search=Ada%20Example&mineral=铜&page_size=1"
    )
    assert searched.json()["total"] == 2 and searched.json()["has_more"]
    next_page = await client.get("/api/frontier?page_size=1&page=2")
    assert next_page.json()["items"][0]["id"] != data["items"][0]["id"]
    assert (await client.get(f"/api/frontier/{business['ids'][3]}")).status_code == 404
    assert (await client.get(f"/api/frontier/{business['ids'][2]}")).status_code == 404
    assert (await client.get("/api/frontier?direction=invalid")).status_code == 422
    assert (await client.get("/api/frontier?page_size=500")).status_code == 422


async def test_academic_processing_is_chinese_and_retains_missing_abstract_scope(
    monkeypatch,
):
    from pipeline.processors import academic
    from pipeline.processors.enrich import enrich

    generate = AsyncMock(return_value={"title_zh": "铜尾矿浮选回收率提高20%"})
    monkeypatch.setattr(academic, "complete_json", generate)
    result = await enrich(
        "Copper tailings flotation recovery improves by 20%",
        "Copper tailings flotation recovery improves by 20%",
        "en",
        8,
        source=source(),
        published_at=datetime.now(UTC),
        metadata={
            "doi": "10.5555/copper-test",
            "authors": ["Ada Example"],
            "journal": "TEST JOURNAL",
            "abstract_available": False,
        },
    )
    assert result["category"] == "report" and result["quality_score"] >= 70
    assert "暂未提供摘要" in result["summary_zh"] and not result["is_translated"]
    assert "铜" in result["minerals"]
    generate.assert_awaited_once()
