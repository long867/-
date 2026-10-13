"""Transparent topic labels indicate reporting subjects, not verified risk levels."""

from typing import Literal

CountryTopic = Literal["policy", "trade", "projects", "supply_chain", "investment"]
TOPIC_PATTERNS = {
    "policy": (
        r"政策|法规|许可|矿业法|税收|环保|监管|regulation|legislation|permitt?ing|"
        r"royalt(y|ies)|mining code|environmental|taxation"
    ),
    "trade": (
        r"出口管制|出口限制|出口禁令|禁止出口|出口配额|禁运|制裁|关税|"
        r"export.{0,35}(ban|restrict|control|quota)|sanctions|tariffs|embargo"
    ),
    "projects": (
        r"矿山|矿场|矿床|勘探|钻探|矿产项目|开采|资源量|mining project|"
        r"mine development|exploration|drilling|mineral resource|ore reserve"
    ),
    "supply_chain": (
        r"供应链|停产|罢工|供应中断|冶炼|精炼|物流|supply chain|production halt|"
        r"strike|smelt(er|ing)|refiner(y|ies)|supply disruption|logistics"
    ),
    "investment": (
        r"投资|融资|收购|并购|投产|募资|investment|financing|acquisition|"
        r"merger|funding|capital rais|commissioning"
    ),
}
TOPIC_LABELS = {
    "policy": "政策与监管",
    "trade": "出口与贸易",
    "projects": "矿山与勘探",
    "supply_chain": "供应链与生产",
    "investment": "投资与交易",
}
