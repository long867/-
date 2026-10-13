"""Deterministic editorial processing of verified, already-Chinese spot quotes."""

from datetime import datetime
from typing import Any

from app.schemas.api import PriceInput
from pipeline.processors.extractor import quality_score


def process_price(
    title: str,
    content: str,
    raw_json: dict[str, Any],
    authority: int,
    published_at: datetime | None,
    region: str | None,
) -> dict[str, Any]:
    """Keep the observed value, commodity scope, source date and unit intact."""
    quote = PriceInput.model_validate(raw_json["price_observation"])
    literal = str(raw_json["price_observation"]["price"])
    if (
        literal not in content
        or quote.price_type not in {"spot", "benchmark"}
        or quote.currency != "CNY"
        or "元/" + quote.unit not in content
    ):
        raise ValueError("Price metadata does not match verified public evidence")
    kind = "现货价格" if quote.price_type == "spot" else "公开参考价"
    product = quote.product or quote.mineral
    summary = (
        f"{quote.source_name or '生意社'}{quote.date}公开资料显示，{product}的{kind}为"
        f"{literal}元/{quote.unit}，币种为人民币。该记录保留原始报价日期，"
        "与最近采集时间分别展示；休市或信源未发布新价时保留最近报价。"
        "不同品级、加工产品、现货与期货价格不能混用，涨跌幅仅与同一来源、"
        "相同单位的前一观测比较，不能凭单次报价推断全年趋势。"
    )
    return {
        "title_zh": title,
        "summary": summary,
        "summary_zh": summary,
        "content_zh": content,
        "is_translated": False,
        "minerals": [quote.mineral],
        "regions": [region] if region and region != "全球" else [],
        "companies": [],
        "projects": [],
        "policy_names": [],
        "tags": [product.split("（")[0], kind],
        "category": "price",
        "quality_score": quality_score(authority, content, published_at),
        "relevance_score": 100.0,
    }
