"""Collector failure boundaries, pagination, editorial validation and copy detection."""

import gzip
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import httpx
import pytest
import respx
from app.core.config import Settings

from pipeline.config.catalog import load_sources
from pipeline.fetchers.api_fetcher import APIFetcher
from pipeline.fetchers.rss_fetcher import RSSFetcher
from pipeline.fetchers.transport import FetchTransport, RobotsDenied, retry_after
from pipeline.processors.dedup import (
    hamming_distance,
    is_duplicate_title,
    normalize_url,
    simhash,
)
from pipeline.processors.extractor import freshness, quality_score
from pipeline.processors.translator import split_translation, translate
from pipeline.schemas import RawArticle, SourceDefinition


def source(kind: str = "api", **config) -> SourceDefinition:
    return SourceDefinition(
        name="Test",
        url="https://public.example/feed",
        type=kind,
        category="news",
        authority_score=9,
        parser_config=config,
    )


def response(payload, status=200, **headers) -> httpx.Response:
    return httpx.Response(
        status,
        json=payload,
        headers=headers,
        request=httpx.Request("GET", "https://public.example/feed"),
    )


def test_catalog_covers_requested_groups() -> None:
    catalog = load_sources()
    assert len(catalog) >= 38
    assert {row.category for row in catalog} == {
        "news",
        "price",
        "policy",
        "report",
        "company",
    }
    assert {row.language for row in catalog} >= {"en", "zh", "es"}
    assert all(1 <= row.authority_score <= 10 for row in catalog)


def test_normalize_url_and_copy_fingerprint() -> None:
    assert (
        normalize_url(
            "https://EXAMPLE.com/news?id=1&ref=homepage&fbclid=z&utm_medium=rss#x"
        )
        == "https://example.com/news?id=1"
    )
    assert is_duplicate_title(
        "BHP expands copper mine in Chile", "BHP expands copper mine in Chile!"
    )
    text = "BHP copper mine production in Chile increased 12 percent. " * 15
    assert hamming_distance(simhash(text), simhash(text + " Update.")) <= 3
    assert simhash(text) != simhash("Lithium exports in Australia declined.")


def test_freshness_and_quality_have_expected_weights() -> None:
    now = datetime.now(UTC)
    assert freshness(now - timedelta(days=7), now) == pytest.approx(0.5)
    assert freshness(None, now) == 0.3
    content = "Copper project production rose 12% according to a company report. " * 40
    assert quality_score(10, content, now) - quality_score(
        5, content, now
    ) == pytest.approx(20)
    assert quality_score(10, content, now) > quality_score(
        10, content, now - timedelta(days=30)
    )


def test_translation_split_is_lossless() -> None:
    text = ("BHP copper mine in Chile.\n" * 70) + "尾段"
    parts = split_translation(text, 500)
    assert "".join(parts) == text and max(map(len, parts)) <= 500


async def test_paginated_api_keeps_evidence_and_rejects_external_next() -> None:
    row = {
        "title": "Copper in Chile",
        "content": "BHP increased copper mine output by 10% in Chile.",
        "url": "/article/1",
    }
    transport = FetchTransport({})
    transport.get = AsyncMock(
        side_effect=[
            response({"items": [row], "next": "/page2"}),
            response({"items": [{**row, "url": "/article/2"}], "next": None}),
        ]
    )
    fetcher = APIFetcher(
        source(records_path="items", pagination={"mode": "next_url"}), transport
    )
    assert len(await fetcher.fetch()) == 2
    assert fetcher.result.etag is None
    transport.get = AsyncMock(
        return_value=response({"items": [row], "next": "http://127.0.0.1/private"})
    )
    fetcher = APIFetcher(
        source(records_path="items", pagination={"mode": "next_url"}), transport
    )
    with pytest.raises(ValueError, match="Cross-origin"):
        await fetcher.fetch()


async def test_page_failure_does_not_return_an_advanced_checkpoint() -> None:
    row = {"title": "Copper", "content": "Copper production.", "url": "/article/1"}
    transport = FetchTransport({})
    transport.get = AsyncMock(
        side_effect=[
            response({"items": [row], "next": "cursor2"}),
            httpx.ReadTimeout("transient"),
        ]
    )
    fetcher = APIFetcher(
        source(records_path="items", pagination={"mode": "cursor"}),
        transport,
        state={"cursor": "cursor1"},
    )
    with pytest.raises(httpx.ReadTimeout):
        await fetcher.fetch()
    assert not fetcher.result.articles


async def test_rss_uses_feed_evidence_when_article_is_denied() -> None:
    xml = (
        b'<rss version="2.0"><channel><title>News</title><item>'
        b"<title>BHP copper in Chile</title><link>https://public.example/a</link>"
        b"<description>BHP increased copper production in Chile by 12 percent."
        b"</description></item></channel></rss>"
    )
    transport = FetchTransport({})
    transport.get = AsyncMock(
        side_effect=[
            httpx.Response(
                200,
                content=xml,
                request=httpx.Request("GET", "https://public.example/feed"),
            ),
            RobotsDenied("blocked"),
        ]
    )
    fetcher = RSSFetcher(source("rss"), transport)
    rows = await fetcher.fetch()
    assert len(rows) == 1 and rows[0].language == "en"
    assert rows[0].raw_json["full_text"] is False
    assert rows[0].published_at is None and len(fetcher.result.errors) == 1


async def test_invalid_summary_and_partial_translation_are_not_accepted(
    monkeypatch,
) -> None:
    import pipeline.processors.translator as module

    monkeypatch.setattr(
        module, "get_settings", lambda: Settings(LLM_API_KEY="fixture", _env_file=None)
    )
    monkeypatch.setattr(
        module,
        "complete_json",
        AsyncMock(
            return_value={"title_zh": "铜矿", "summary": "Copper", "summary_zh": "太短"}
        ),
    )
    with pytest.raises(ValueError, match="editorial"):
        await translate("Copper", "BHP copper mine in Chile.", "en")
    summary = {
        "title_zh": "智利铜矿扩产",
        "summary": "BHP copper in Chile.",
        "summary_zh": (
            "据原文披露，BHP在智利推进铜矿生产计划，相关信息涉及铜矿项目运营和产量变化。"
            "报道说明了公司名称、所在国家和矿种，提供了该项目的背景。"
            "原文未披露新的投资金额、建设时间或政策影响，"
            "因此不能据此推断未来价格走势或新增产能规模。"
        ),
    }
    monkeypatch.setattr(
        module,
        "complete_json",
        AsyncMock(side_effect=[summary, {"content_zh": ""}, {"content_zh": ""}]),
    )
    with pytest.raises(ValueError, match="Incomplete"):
        await translate("Copper", "BHP copper mine in Chile.", "en")


async def test_summary_retry_receives_length_feedback(monkeypatch) -> None:
    """A rejected first draft receives correction information before retrying."""
    import json

    import pipeline.processors.translator as module

    monkeypatch.setattr(
        module, "get_settings", lambda: Settings(LLM_API_KEY="fixture", _env_file=None)
    )
    summary = {
        "title_zh": "铜矿产量变化",
        "summary": "Copper output increased by 10%.",
        "summary_zh": "太短",
    }
    valid = (
        "据原文披露，智利铜矿产量增长10%，报道提供了当地铜矿生产变化的依据。"
        "这一数据描述的是原文所述生产情况，不能直接作为市场价格变化的证据。"
        "原文没有说明价格、币种、投资金额或未来产量目标，"
        "因此咨询回答应区分生产事实与尚未得到材料支持的市场预测。"
    )
    generation = AsyncMock(
        side_effect=[
            summary,
            {**summary, "summary_zh": valid},
            {"content_zh": "铜矿产量增长10%。"},
        ]
    )
    monkeypatch.setattr(module, "complete_json", generation)
    result = await translate("Copper output", "Copper output increased by 10%.", "en")
    assert result["summary_zh"] == valid and result["is_translated"]
    retry = json.loads(generation.await_args_list[1].args[1])
    assert retry["validation_feedback"]["previous_summary_characters"] == 2
    assert retry["summary_zh_characters"]["target"] == 160


def test_numeric_consistency_accepts_word_counts_but_rejects_invented_values():
    """Five→5 is faithful; losing a measured length or adding nine is rejected."""
    from pipeline.processors.translator import numeric_translation_valid

    source = "A 257-metre four-metre ramp. The portfolio has five operating mines."
    assert numeric_translation_valid(source, "斜坡长257米、宽4米，公司运营5座矿山。")
    assert not numeric_translation_valid(
        source, "斜坡长258米、宽4米，公司运营5座矿山。"
    )
    assert not numeric_translation_valid(
        source, "斜坡长257米、宽4米，公司运营9座矿山。"
    )


def test_numeric_masking_roundtrip_keeps_price_precision_and_repeated_values():
    """Model input can hide numbers while restoration retains exact source text."""
    from pipeline.processors.translator import (
        mask_numeric_literals,
        restore_numeric_literals,
    )

    original = "On 2026/10/09: 3,000 tonnes; USD 0.46; rise 6.9%; again USD 0.46."
    masked, literals = mask_numeric_literals(original)
    assert "0.46" not in masked and "2026" not in masked
    assert len(literals) == 7
    assert restore_numeric_literals(masked, literals) == original


async def test_translation_retry_rejects_added_numbers_then_accepts_correction(
    monkeypatch,
):
    """Numeric feedback repairs drafts without relaxing the evidence gate."""
    import json

    import pipeline.processors.translator as module

    monkeypatch.setattr(
        module, "get_settings", lambda: Settings(LLM_API_KEY="fixture", _env_file=None)
    )
    summary = {
        "title_zh": "铜矿",
        "summary": "Copper output rose 10%.",
        "summary_zh": (
            "据原文披露，智利铜矿产量增长10%，报道提供了当地铜矿生产变化的依据。"
            "这一数据描述的是原文所述生产情况，不能直接作为市场价格变化的证据。"
            "原文没有说明价格、币种、投资金额或未来产量目标，"
            "因此咨询回答应区分生产事实与尚未得到材料支持的市场预测。"
        ),
    }
    generation = AsyncMock(
        side_effect=[
            summary,
            {"content_zh": "铜矿产量增长10%，投资99亿美元。"},
            {"content_zh": "铜矿产量增长10%。"},
        ]
    )
    monkeypatch.setattr(module, "complete_json", generation)
    result = await translate("Copper", "Copper output rose 10%.", "en")
    assert result["content_zh"] == "铜矿产量增长10%。"
    retry = json.loads(generation.await_args_list[2].args[1])
    assert retry["validation_feedback"]["unexpected_numeric_counts"] == {"99": 1}


@respx.mock
async def test_transport_decompresses_once_and_pins_checked_ip(monkeypatch) -> None:
    import pipeline.fetchers.transport as module

    monkeypatch.setattr(module, "validate_public_url", AsyncMock())
    monkeypatch.setattr(
        module, "public_addresses", AsyncMock(return_value=["93.184.216.34"])
    )
    transport = FetchTransport({})
    transport.robots = AsyncMock(return_value=0)
    transport.pace = AsyncMock()
    route = respx.get("https://93.184.216.34/feed").mock(
        return_value=httpx.Response(
            200,
            content=gzip.compress(b"original evidence"),
            headers={"content-encoding": "gzip"},
        )
    )
    result = await transport.get("https://public.example/feed")
    assert (
        result.text == "original evidence"
        and str(result.url) == "https://public.example/feed"
    )
    request = route.calls.last.request
    assert request.headers["host"] == "public.example"
    assert request.extensions["sni_hostname"] == "public.example"


@respx.mock
async def test_robots_exclusion_is_enforced(monkeypatch) -> None:
    import pipeline.fetchers.transport as module

    monkeypatch.setattr(module, "validate_public_url", AsyncMock())
    monkeypatch.setattr(
        module, "public_addresses", AsyncMock(return_value=["93.184.216.34"])
    )
    transport = FetchTransport({})
    transport.pace = AsyncMock()
    respx.get("https://93.184.216.34/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nDisallow: /private")
    )
    with pytest.raises(RobotsDenied):
        await transport.get("https://public.example/private")


def test_retry_after_is_bounded() -> None:
    assert retry_after("9000") == 120
    assert retry_after("invalid") == 0
    assert retry_after("-3") == 0


async def test_api_window_resumes_at_next_unconsumed_page() -> None:
    row = {"title": "Copper", "content": "Copper production.", "url": "/a"}
    transport = FetchTransport({})
    transport.get = AsyncMock(return_value=response({"items": [row], "next": "/page2"}))
    config = source(
        records_path="items", pagination={"mode": "next_url", "max_pages": 1}
    )
    first = APIFetcher(config, transport)
    assert len(await first.fetch()) == 1
    assert first.result.state["next_url"] == "https://public.example/page2"
    second = APIFetcher(config, transport, state=first.result.state)
    await second.fetch()
    assert transport.get.await_args.args[0] == "https://public.example/page2"


async def test_sec_filters_forms_before_applying_item_budget() -> None:
    transport = FetchTransport({})
    transport.get = AsyncMock(
        return_value=response(
            {
                "filings": {
                    "recent": {"form": ["4", "10-K"], "accessionNumber": ["a", "b"]}
                }
            }
        )
    )
    fetcher = APIFetcher(
        source(
            adapter="sec_submissions",
            record_format="columnar",
            records_path="filings.recent",
            forms=["10-K"],
            max_items=1,
        ),
        transport,
    )
    fetcher.sec_filing = AsyncMock(
        return_value=RawArticle(
            source_name="Test",
            title="Annual report",
            content="Copper report.",
            url="https://public.example/report",
            language="en",
            category="company",
        )
    )
    assert len(await fetcher.fetch()) == 1
    assert fetcher.sec_filing.await_args.args[0]["form"] == "10-K"


async def test_api_rejects_partial_page_cursor_advancement() -> None:
    row = {"title": "Copper", "content": "Copper production.", "url": "/a"}
    transport = FetchTransport({})
    transport.get = AsyncMock(
        return_value=response({"items": [row, row], "next": "next"})
    )
    fetcher = APIFetcher(
        source(max_items=1, records_path="items", pagination={"mode": "cursor"}),
        transport,
    )
    with pytest.raises(ValueError, match="item budget"):
        await fetcher.fetch()


async def test_api_missing_permalink_is_rejected() -> None:
    transport = FetchTransport({})
    transport.get = AsyncMock(
        return_value=response(
            [{"title": "Copper production", "content": "BHP copper in Chile."}]
        )
    )
    with pytest.raises(ValueError, match="nonempty strings"):
        await APIFetcher(source(), transport).fetch()


async def test_yahoo_price_units_and_timestamps_are_preserved() -> None:
    transport = FetchTransport({})
    transport.get = AsyncMock(
        return_value=response(
            {
                "chart": {
                    "result": [
                        {
                            "meta": {"currency": "USD", "symbol": "HG=F"},
                            "timestamp": [1791590400, 1791676800],
                            "indicators": {"quote": [{"close": [4.25, None]}]},
                        }
                    ],
                    "error": None,
                }
            }
        )
    )
    config = source(
        adapter="yahoo_chart", constants={"mineral": "铜（COMEX期货）", "unit": "lb"}
    )
    config.category = "price"
    fetcher = APIFetcher(config, transport)
    rows = await fetcher.fetch()
    assert len(rows) == 1 and len(fetcher.result.prices) == 1
    price = fetcher.result.prices[0]
    assert price["price"] == "4.250000" and price["unit"] == "lb"
    assert price["currency"] == "USD" and price["mineral"] == "铜（COMEX期货）"


@respx.mock
async def test_transport_retries_429_but_not_403(monkeypatch) -> None:
    import pipeline.fetchers.transport as module

    monkeypatch.setattr(module, "validate_public_url", AsyncMock())
    monkeypatch.setattr(
        module, "public_addresses", AsyncMock(return_value=["93.184.216.34"])
    )
    transport = FetchTransport({})
    transport.robots = AsyncMock(return_value=0)
    transport.pace = AsyncMock()
    route = respx.get("https://93.184.216.34/feed").mock(
        side_effect=[httpx.Response(429), httpx.Response(200, text="ok")]
    )
    assert (await transport.get("https://public.example/feed")).text == "ok"
    assert route.call_count == 2
    route.mock(return_value=httpx.Response(403))
    before = route.call_count
    assert (await transport.get("https://public.example/feed")).status_code == 403
    assert route.call_count - before == 1


@respx.mock
async def test_cross_origin_redirect_does_not_forward_credentials(monkeypatch) -> None:
    import pipeline.fetchers.transport as module

    monkeypatch.setattr(module, "validate_public_url", AsyncMock())
    monkeypatch.setattr(
        module, "public_addresses", AsyncMock(return_value=["93.184.216.34"])
    )
    transport = FetchTransport({"headers": {"Authorization": "fixture-secret"}})
    transport.robots = AsyncMock(return_value=0)
    transport.pace = AsyncMock()
    route = respx.get("https://93.184.216.34/feed").mock(
        side_effect=[
            httpx.Response(302, headers={"location": "https://another.example/feed"}),
            httpx.Response(200, text="ok"),
        ]
    )
    assert (await transport.get("https://public.example/feed")).text == "ok"
    assert "authorization" not in route.calls.last.request.headers


@respx.mock
async def test_doh_rejects_mixed_public_and_private_answers(monkeypatch) -> None:
    import pipeline.fetchers.resolver as module

    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: Settings(
            FETCH_DNS_RESOLVER="https://1.1.1.1/dns-query", _env_file=None
        ),
    )
    module._cache.clear()
    respx.get("https://1.1.1.1/dns-query").mock(
        return_value=response(
            {
                "Status": 0,
                "Answer": [
                    {"type": 1, "data": "93.184.216.34"},
                    {"type": 1, "data": "127.0.0.1"},
                ],
            }
        )
    )
    with pytest.raises(ValueError, match="public IPs"):
        await module.public_addresses("public.example")
