"""数据源工厂：统一入口，同时提供同步与异步方法。

同步方法供 CLI 使用；异步方法供未来 GUI 协程使用。
akshare / yfinance 采用懒加载，未安装时仅在调用对应源时抛错。
"""

from __future__ import annotations

from dataclasses import dataclass

from holdings.exceptions import DataSourceUnavailableError, SymbolNotFoundError
from holdings.models.enums import MarketType

# 异常类现已移至 holdings.exceptions，此处保留重新导出，
# 使 `from holdings.data.fetcher import DataSourceUnavailableError` 等历史路径继续可用。
__all__ = [
    "DataSourceUnavailableError",
    "PriceResult",
    "SymbolNotFoundError",
    "afetch_price",
    "fetch_price",
    "get_fetcher",
]


@dataclass
class PriceResult:
    """单标的报价结果。"""

    symbol: str
    price: float
    currency: str = "CNY"
    source: str = ""


def get_fetcher(market: MarketType):
    """根据市场返回对应 fetcher——**查一次表**，不再是一串 `if market == …`。

    表在 `data/markets.py`：加一个市场是「加一个模块 + 在表里加一行」，本模块
    不用改。此前每加一个市场都要在这里加一个分支，本模块于是成了「市场清单」
    的第二个副本。

    **导入仍放在函数体内**（与改动前一样），为的是避开循环依赖：各市场模块
    要从本模块取 `DataSourceUnavailableError` / `SymbolNotFoundError` /
    `PriceResult`，模块级导入会构成 fetcher → markets → a_stock → fetcher 的环，
    导致 `import holdings.data.fetcher` 直接失败（`holdings sync` 会整条挂掉）。
    """
    from holdings.data import markets

    return markets.fetcher_for(market)


def fetch_price(symbol: str, market: MarketType) -> PriceResult:
    """同步拉取单标的报价。"""
    return get_fetcher(market).fetch(symbol)


async def afetch_price(symbol: str, market: MarketType) -> PriceResult:
    """异步拉取单标的报价（当前通过同步垫片实现，供 GUI 协程调用）。"""
    import asyncio

    return await asyncio.to_thread(fetch_price, symbol, market)
