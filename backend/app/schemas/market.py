"""Public resource directory and independently dated quotation coverage."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.api import PriceOut
from app.schemas.intelligence import FacetOut


class MineralMarketItem(FacetOut):
    symbol: str
    english_name: str
    group: str
    prices: list[PriceOut] = Field(default_factory=list)
    price_status: Literal["available", "stale", "unavailable"]


class MineralMarket(BaseModel):
    items: list[MineralMarketItem]
    total: int
    quoted_minerals: int
    quoted_products: int
    latest_checked_at: datetime | None
    generated_at: datetime
    refresh_schedule: str = "每天 08:30、17:30、20:30（北京时间）"
    quotation_note: str = (
        "公开每日报价；休市保留最近报价，按产品与单位区分，非分钟级行情。"
    )
