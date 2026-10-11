"""Evidence gates for dated spot quotes and numeric translations."""

import json
from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from pipeline.fetchers.price_fetcher import parse_ppi_quote
from pipeline.processors.translator import (
    mask_evidence,
    measurements,
    numeric_translation_valid,
    restore_numeric_literals,
    summary_measurements_valid,
    translate_fragment,
)

TABLE = (
    "<html><title>2026年10月09日商品现货与期货价格对比表</title>"
    "<table><tr><td>碳酸锂</td><td>121000.00</td><td>LC2611</td>"
    "<td>105000</td><td>-13.22%</td></tr></table>"
    "<p>价格单位：黄金为元/克，白银为元/千克，其余元/吨。</p></html>"
)


def test_spot_quote_uses_dated_spot_cell_not_futures_or_percent():
    quote, evidence, _, published = parse_ppi_quote(TABLE, "https://example.com/day")
    assert quote["price"] == "121000.00" and quote["currency"] == "CNY"
    assert quote["date"] == "2026-10-09" and published.isoformat().startswith(
        "2026-10-08"
    )
    assert quote["price_type"] == "spot" and quote["unit"] == "吨"
    assert "105000" in evidence and "LC2611" in evidence
    assert "现货口径" in quote["product"] and "电池级" not in quote["product"]


@pytest.mark.parametrize(
    "html",
    [
        "<script>document.cookie = 'challenge'</script>",
        TABLE.replace("其余元/吨", "其余美元/吨"),
        TABLE.replace("2026年10月09日", "2099年10月09日"),
        TABLE.replace("121000.00", "--"),
        TABLE.replace(
            "</table>", "<tr><td>碳酸锂</td><td>1</td><td>x</td><td>2</td></tr></table>"
        ),
    ],
)
def test_unknown_units_dates_missing_values_and_ambiguous_rows_fail_closed(html):
    with pytest.raises(ValueError):
        parse_ppi_quote(html, "https://example.com/day")


def test_atomic_anchors_preserve_dates_units_magnitude_and_word_measurements():
    original = (
        "On September 30, 2026, US$5 million rose 6.9%; a 257-metre "
        "four-metre by 4.5-metre ramp connects two operations."
    )
    masked, anchors = mask_evidence(original)
    assert "two operations" in masked and "6.9" not in masked
    assert "September 30, 2026" in anchors.values()
    assert "four-metre" in anchors.values()
    assert restore_numeric_literals(masked, anchors) == original
    assert measurements("US$5 million; 6.9%; 257 metres") != measurements(
        "US$5 billion; 6.9吨; 257短吨"
    )


def test_signed_values_currency_magnitude_and_unique_metadata_anchors():
    assert not numeric_translation_valid("Change -6.9%", "变化6.9%")
    assert numeric_translation_valid("On 2026-10-09", "2026年10月09日")
    assert summary_measurements_valid("US$5 million", "金额5百万美元")
    assert not summary_measurements_valid("US$5 million", "金额5十亿美元")
    assert summary_measurements_valid("a four-metre ramp", "宽4米")
    title, title_anchors = mask_evidence("2026 outlook")
    content, content_anchors = mask_evidence(
        "Output 10 tonnes", offset=len(title_anchors)
    )
    assert set(title_anchors).isdisjoint(content_anchors)
    assert restore_numeric_literals(title, title_anchors) == "2026 outlook"
    assert restore_numeric_literals(content, content_anchors) == "Output 10 tonnes"


async def test_unit_substitution_retries_even_when_all_numbers_match(monkeypatch):
    import pipeline.processors.translator as module

    mock = AsyncMock(
        side_effect=[{"content_zh": "产量为10米。"}, {"content_zh": "产量为10吨。"}]
    )
    monkeypatch.setattr(module, "complete_json", mock)
    assert await translate_fragment("Output was 10 tonnes.", "{}") == "产量为10吨。"
    retry = json.loads(mock.await_args_list[1].args[1])
    assert retry["validation_feedback"]["missing_placeholders"]


async def test_repeated_percent_anchor_cannot_be_dropped_or_duplicated(monkeypatch):
    import pipeline.processors.translator as module

    monkeypatch.setattr(module, "get_settings", lambda: Settings(_env_file=None))
    monkeypatch.setattr(
        module,
        "complete_json",
        AsyncMock(
            return_value={"content_zh": "增长{{MI_NUM_A}}，又增长{{MI_NUM_A}}。"}
        ),
    )
    with pytest.raises(ValueError, match="numeric/unit"):
        await translate_fragment("Copper rose 10%; nickel rose 10%.", "{}")


async def test_missing_editorial_field_can_use_labeled_fully_validated_translation(
    monkeypatch,
):
    import pipeline.processors.translator as module

    chinese = (
        "据原文披露，BHP在智利推进铜矿生产计划，相关信息涉及铜矿项目运营和产量变化。"
        "报道说明了公司名称、所在国家和矿种，提供了该项目的背景。"
        "原文未披露新的投资金额、建设时间或政策影响，因此不能据此推断未来价格走势或新增产能规模。"
    )
    monkeypatch.setattr(
        module, "get_settings", lambda: Settings(LLM_API_KEY="fixture", _env_file=None)
    )
    missing = {"title_zh": "铜矿生产计划", "summary": "BHP copper production in Chile."}
    mock = AsyncMock(side_effect=[missing, missing, {"content_zh": chinese}])
    monkeypatch.setattr(module, "complete_json", mock)
    result = await module.translate("Copper", "BHP copper production in Chile.", "en")
    assert result["is_translated"]
    assert result["summary_zh"].startswith("【译文摘录】")
    assert 100 <= len(result["summary_zh"]) <= 200
    assert result["content_zh"] == chinese
