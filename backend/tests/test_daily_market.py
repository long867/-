"""Daily price provenance, physical units, holidays and directory contracts."""

from datetime import date
from decimal import Decimal

import pytest

from app.tasks.celery_app import celery_app
from pipeline.config.catalog import load_sources
from pipeline.config.minerals import mineral_catalog
from pipeline.fetchers.daily_price_fetcher import (
    parse_daily_table,
    parse_product_history,
    verified_benchmark,
)
from pipeline.fetchers.price_fetcher import parse_ppi_quotes
from pipeline.processors.price_processor import process_price


def daily_table(day="09/10/2026", old="09-30", new="10-09"):
    return (
        f'<div class="name">100 Spot Commodities Price Chart - {day}</div>'
        f"<table><tr><td>Commodity</td><td>Sectors</td><td>{old}</td><td>{new}</td><td>Change</td></tr>"
        '<tr><td><a href="prodetail-1771.html">Germanium</a></td><td>Metals</td>'
        "<td>27,000.50</td><td>27,016.67</td><td>0.06%</td></tr></table>"
    )


def reference(unit="元/千克", value="27016.67", stamp="10-09 16:20", name="锗"):
    return (
        f'<span class="pricename">{name}</span>'
        f'<span class="price-fb01_1">{value}</span>'
        f'<span class="price-fb01_2">{unit}</span>'
        f'<li class="post_date_li">更新时间：{stamp}</li>'
    )


def test_daily_dates_are_from_header_and_units_from_same_product_reference():
    current, previous, rows = parse_daily_table(daily_table())
    assert current == date(2026, 10, 9) and previous == date(2026, 9, 30)
    assert rows["1771"][2] == "27016.67"
    unit, proof = verified_benchmark(
        reference(), current, rows["1771"][2], {"verify_name": "锗"}
    )
    assert unit == "千克" and "元/千克" in proof


@pytest.mark.parametrize(
    "html",
    [
        reference(unit="美元/吨"),
        reference(value="123"),
        reference(stamp="10-08"),
        reference(name="铜"),
        "<script>challenge</script>",
    ],
)
def test_ambiguous_reference_or_changed_unit_is_not_guessed(html):
    with pytest.raises(ValueError):
        verified_benchmark(html, date(2026, 10, 9), "27016.67", {"verify_name": "锗"})


def test_year_boundary_and_no_invented_holiday_quotes():
    current, previous, _ = parse_daily_table(
        daily_table("02/01/2026", "12-31", "01-02")
    )
    assert current == date(2026, 1, 2) and previous == date(2025, 12, 31)
    with pytest.raises(ValueError):
        parse_daily_table(daily_table("09/10/2026", new="10-10"))
    with pytest.raises(ValueError):
        parse_daily_table(daily_table("09/10/2099"))


def test_product_history_keeps_explicit_dates_and_rejects_other_products():
    html = (
        "<table><tr><td>Germanium</td><td>Metals</td><td>27016.67</td>"
        "<td>2026-10-09</td></tr><tr><td>Copper</td><td>Metals</td>"
        "<td>100</td><td>2026-10-09</td></tr></table>"
    )
    assert parse_product_history(html, "Germanium") == [(date(2026, 10, 9), "27016.67")]
    with pytest.raises(ValueError):
        parse_product_history(html, "Gold")


def test_spot_products_preserve_gold_silver_and_wet_ore_units():
    rows = [("黄金", "900"), ("白银", "14000"), ("铁矿石", "670"), ("碳酸锂", "114000")]
    html = "<title>2026年10月09日商品现货与期货价格对比表</title><table>"
    html += "".join(
        f"<tr><td>{name}</td><td>{value}</td><td>合约</td><td>999</td></tr>"
        for name, value in rows
    )
    html += (
        "</table><p>价格单位：黄金为元/克，白银为元/千克，其余元/吨。</p>"
        "<p>铁矿石现货为湿吨，期货为干吨。</p>"
    )
    quotes = [item[0] for item in parse_ppi_quotes(html, "https://example.com/table")]
    assert [q["unit"] for q in quotes] == ["克", "千克", "湿吨", "吨"]
    assert all(Decimal(q["price"]) != 999 for q in quotes)
    assert quotes[-1]["source"].endswith("1162.html#spot")
    wet_quote, wet_evidence, _, published = next(
        item
        for item in parse_ppi_quotes(html, "https://example.com/table")
        if item[0]["mineral"] == "铁矿石"
    )
    processed = process_price(
        "铁矿石报价",
        wet_evidence,
        {"price_observation": wet_quote},
        8,
        published,
        "中国",
    )
    assert "元/湿吨" in processed["summary_zh"]
    without_wet_note = html.replace("铁矿石现货为湿吨，期货为干吨。", "未知口径")
    assert "铁矿石" not in {
        item[0]["mineral"]
        for item in parse_ppi_quotes(without_wet_note, "https://example.com/table")
    }


def test_directory_and_daily_schedule_have_no_licensed_feed_dependency():
    catalog = mineral_catalog()
    assert len(catalog) == 100 and len({item["name"] for item in catalog}) == 100
    assert {"金", "锂", "钨", "锗", "萤石", "石墨", "钕", "铌"} <= {
        item["name"] for item in catalog
    }
    sources = load_sources()
    public = [s for s in sources if s.active and s.category == "price"]
    assert {s.parser_config["adapter"] for s in public} == {
        "ppi_spot_market",
        "sunsirs_mineral_daily",
    }
    assert all(not s.parser_config.get("requires_license") for s in public)
    schedule = celery_app.conf.beat_schedule["daily-public-prices"]
    assert schedule["schedule"].hour == {8, 17, 20} and schedule["schedule"].minute == {
        30
    }
    celery_app.loader.import_default_modules()
    assert celery_app.tasks[schedule["task"]].max_retries == 3


def test_price_editorial_processing_preserves_non_lithium_units_and_scope():
    quote = {
        "mineral": "锗",
        "product": "金属锗",
        "price": "27016.67",
        "unit": "千克",
        "currency": "CNY",
        "date": "2026-10-09",
        "source": "https://example.com/series",
        "price_type": "benchmark",
    }
    values = process_price(
        "金属锗报价",
        "金属锗参考价27016.67元/千克",
        {"price_observation": quote},
        8,
        None,
        "中国",
    )
    assert values["minerals"] == ["锗"] and "27016.67元/千克" in values["summary_zh"]
    with pytest.raises(ValueError):
        process_price(
            "报价", "27016.67元/吨", {"price_observation": quote}, 8, None, "中国"
        )
