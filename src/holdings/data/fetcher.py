"""数据源工厂：统一入口，同时提供同步与异步方法。

同步方法供 CLI 使用；异步方法供未来 GUI 协程使用。
akshare / yfinance 采用懒加载，未安装时仅在调用对应源时抛错。
"""

from __future__ import annotations

from dataclasses import dataclass

from holdings.models.enums import MarketType


class DataSourceUnavailableError(Exception):
    """数据源不可用或超时。"""


class SymbolNotFoundError(Exception):
    """标的代码不存在或无法识别。"""


@dataclass
class PriceResult:
    """单标的报价结果。"""

    symbol: str
    price: float
    currency: str = "CNY"
    source: str = ""


def get_fetcher(market: MarketType):
    """根据市场返回对应 fetcher。

    三个子模块都要从本模块导入 `DataSourceUnavailableError` / `SymbolNotFoundError` /
    `PriceResult`，故此处必须延迟导入，否则与模块级导入构成循环依赖，
    导致 `import holdings.data.fetcher` 直接失败（`holdings sync` 会整条挂掉）。
    """
    from holdings.data.a_stock import AStockFetcher
    from holdings.data.gold import GoldFetcher
    from holdings.data.us_stock import USStockFetcher

    if market == MarketType.A_SHARE:
        return AStockFetcher()
    if market == MarketType.US_STOCK:
        return USStockFetcher()
    if market == MarketType.GOLD:
        return GoldFetcher()
    raise SymbolNotFoundError(f"未知市场：{market}")


def fetch_price(symbol: str, market: MarketType) -> PriceResult:
    """同步拉取单标的报价。"""
    return get_fetcher(market).fetch(symbol)


async def afetch_price(symbol: str, market: MarketType) -> PriceResult:
    """异步拉取单标的报价（当前通过同步垫片实现，供 GUI 协程调用）。"""
    import asyncio

    return await asyncio.to_thread(fetch_price, symbol, market)
