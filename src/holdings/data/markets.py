"""市场注册表：哪个市场用哪个 fetcher。

**加一个市场 = 加一个模块 + 在 `FETCHERS` 里加一行**，`fetcher.py` 一个字
不用改——这与 `data/brokers/` 加一家券商是同一套写法（那里的判据是
「加第三家券商，`import_cmd.py` 一行未改」，见 BACKLOG B-28）。

**这张表放在单独一个模块里，而不是 `fetcher.py` 里**，为的是避开循环导入：
各市场模块要从 `fetcher.py` 取 `PriceResult` 与两个异常类（见 `fetcher.py`
里那段说明），而这里反过来要 import 它们。`fetcher.get_fetcher` 因此把这个
模块的导入放在函数体内。

**一个市场只登记一次**：键就是 `MarketType`，重复登记在字典字面量里是语法
上的重复键，写错当场就报错，不会静默丢掉其中一个。

各市场的**数据源**由各自模块声明（`a_stock.py` 的 `{"akshare": …, "yfinance": …}`），
键就是 `data_sources.priority` 里写的名字；这里的表只管「市场 → 取价入口」。
"""

from __future__ import annotations

from typing import Protocol

from holdings.data.a_stock import AStockFetcher
from holdings.data.fetcher import PriceResult
from holdings.data.gold import GoldFetcher
from holdings.data.us_stock import USStockFetcher
from holdings.exceptions import SymbolNotFoundError
from holdings.models.enums import MarketType


class Fetcher(Protocol):
    """一个市场的取价入口。

    三家的实现没有共同基类，只有这一条约定——**先不抽基类**：这个项目已经
    吃过一次「先写通用件、结果没人用」的亏（BACKLOG B-12 的零引用模块），
    等第四个市场出现、形状确实一样时再说。
    """

    def fetch(self, symbol: str) -> PriceResult: ...


#: 市场 → fetcher 类。
FETCHERS: dict[MarketType, type[Fetcher]] = {
    MarketType.A_SHARE: AStockFetcher,
    MarketType.US_STOCK: USStockFetcher,
    MarketType.GOLD: GoldFetcher,
}


def fetcher_for(market: MarketType) -> Fetcher:
    """取该市场的 fetcher 实例。

    没登记的市场抛出与改动前一致的错误：`get_fetcher` 原先是一串
    `if market == …` 加一句 `raise SymbolNotFoundError(f"未知市场：{market}")`，
    换手时错误类型与文案都没动，只是判断从「逐个数过」变成了「查一次表」。
    """
    try:
        fetcher_class = FETCHERS[market]
    except KeyError:
        raise SymbolNotFoundError(f"未知市场：{market}") from None
    return fetcher_class()
