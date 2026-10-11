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
        or quote.mineral != "锂"
        or quote.price_type != "spot"
        or quote.currency != "CNY"
        or quote.unit != "吨"
    ):
        raise ValueError("Price metadata does not match verified lithium spot evidence")
    summary = (
        f"生意社{quote.date}公开现期表显示，碳酸锂现货价格为{literal}元/吨，币种为人民币。"
        "这一记录取自表中的现货价格列，期货合约、结算价及现期差属于另外的指标，不混作现货报价。"
        "原表没有明确标注碳酸锂品级，因此该数据不能直接当作电池级碳酸锂或锂矿石报价，"
        "也不能凭单日记录判断全年趋势。"
    )
    return {
        "title_zh": title,
        "summary": summary,
        "summary_zh": summary,
        "content_zh": content,
        "is_translated": False,
        "minerals": ["锂"],
        "regions": [region] if region and region != "全球" else [],
        "companies": [],
        "projects": [],
        "policy_names": [],
        "tags": ["碳酸锂", "现货价格"],
        "category": "price",
        "quality_score": quality_score(authority, content, published_at),
        "relevance_score": 100.0,
    }
