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
    #: 这笔是从哪来的：对账单的格式名（`csv` / `demo-a`）。手录的没有这一项，
    #: 值为 None——「不知道来源」与「来源是空字符串」是两回事。
    source: str | None = None
    #: 券商流水号。有它就能精确判重，没有才退到指纹（见 `dedupe_key`）。
    external_id: str | None = None
    id: int | None = None


def dedupe_key(tx: Transaction) -> tuple:
    """这笔交易在「是不是同一笔」这件事上的身份。

    有券商流水号就用它——那是券商自己给的唯一标识，比任何指纹都硬。

    没有则退到**全字段指纹**（标的 + 日期 + 类型 + 数量 + 价格 + 费用）。
    指纹认不出「同一天分两次、同价同费各买 100 股」这种真实的两笔成交，
    会把后一笔当成重复，所以它只用来**报出来**给人判断，不静默丢弃
    （`import --dedupe` 的默认行为就是报错而非跳过）。
    """
    if tx.external_id:
        return ("external", tx.source, tx.external_id)
    return (
        "fingerprint",
        tx.symbol,
        tx.trade_date.isoformat(),
        tx.trade_type.value,
        tx.quantity,
        tx.price,
        tx.fee,
    )
