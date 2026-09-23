"""示例格式 A：全中文表头、费用拆成三列、市场写作「上海 / 深圳」。

**这不是任何一家真实券商的格式。**它是为了让注册表、自动识别与 `--broker`
三条路都能被真的跑一遍而造的夹具，也是 B-30 写真实解析器时的模板。

真实的解析器等真实样本（BACKLOG B-30）：对着想象的格式写映射表，写出来的
是一堆没人验证过的猜测，而猜错的代价是整批数字错。
"""

from __future__ import annotations

from typing import ClassVar

from holdings.data.brokers.base import BrokerParser
from holdings.models.enums import MarketType, TradeType


class DemoA(BrokerParser):
    name = "demo-a"
    label = "示例格式 A"

    columns: ClassVar[dict[str, tuple[str, ...]]] = {
        "symbol": ("证券代码",),
        "trade_date": ("成交日期",),
        "trade_type": ("业务名称",),
        "quantity": ("成交数量",),
        "price": ("成交均价",),
        "market": ("交易市场",),
    }
    #: 只翻「买入」的几种写法，够说明问题即可；分红 / 送转这些留给
    #: `classify_trade_type`，所有券商共用一份。
    trade_types: ClassVar[dict[str, str]] = {
        "证券买入": TradeType.BUY.value,
        "买入": TradeType.BUY.value,
        "申购": TradeType.BUY.value,
        "证券卖出": TradeType.SELL.value,
        "卖出": TradeType.SELL.value,
    }
    markets: ClassVar[dict[str, str]] = {
        "上海": MarketType.A_SHARE.value,
        "深圳": MarketType.A_SHARE.value,
        "北京": MarketType.A_SHARE.value,
    }
    fee_columns: ClassVar[tuple[str, ...]] = ("佣金", "印花税", "过户费")
