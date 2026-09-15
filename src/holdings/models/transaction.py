"""交易记录数据模型（DTO）。"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from holdings.models.enums import AssetType, MarketType, TradeType


class Transaction(BaseModel):
    """一笔交易记录，字段与数据库 `transactions` 表一一对应。"""

    symbol: str
    market: MarketType
    asset_type: AssetType
    trade_date: date
    trade_type: TradeType
    quantity: float = 0.0
    price: float = 0.0
    fee: float = 0.0
    portfolio_group: str = Field(default="默认")
    notes: str | None = None
    id: int | None = None
