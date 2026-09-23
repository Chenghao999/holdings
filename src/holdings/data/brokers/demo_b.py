"""示例格式 B：列名与 A 全不一样、业务标志本身就是英文、费用只有一列。

与 A 成对：A 演示「表头与取值都是中文、费用拆三列」，B 演示「中文表头里夹着
英文取值、费用只有一列」。两家都只是夹具，理由见 `demo_a` 的模块说明。
"""

from __future__ import annotations

from typing import ClassVar

from holdings.data.brokers.base import BrokerParser
from holdings.models.enums import MarketType


class DemoB(BrokerParser):
    name = "demo-b"
    label = "示例格式 B"

    columns: ClassVar[dict[str, tuple[str, ...]]] = {
        "symbol": ("股票代码",),
        "trade_date": ("发生日期",),
        "trade_type": ("业务标志",),
        "quantity": ("成交股数",),
        "price": ("成交价格",),
        "market": ("市场",),
    }
    #: 这家只把自家叫法翻过来；`业务标志` 直接写 `BUY` / `SELL` 的行原样
    #: 落到 `classify_trade_type` 上，一样认得出。
    trade_types: ClassVar[dict[str, str]] = {
        "普通买入": "BUY",
        "普通卖出": "SELL",
    }
    markets: ClassVar[dict[str, str]] = {
        "沪市": MarketType.A_SHARE.value,
        "深市": MarketType.A_SHARE.value,
    }
    fee_columns: ClassVar[tuple[str, ...]] = ("手续费",)
