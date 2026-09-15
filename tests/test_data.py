"""data 层（fetcher 工厂）的单元测试。

不触网：只验证导入链与工厂分发，不调用任何真实行情接口。
"""

import pytest

from holdings.data import fetcher
from holdings.data.a_stock import AStockFetcher
from holdings.data.gold import GoldFetcher
from holdings.data.us_stock import USStockFetcher
from holdings.models.enums import MarketType


def test_data_layer_imports_without_circular_dependency():
    """回归测试：fetcher 与三个子模块互相导入，曾构成循环依赖。

    一旦有人把 `get_fetcher` 里的延迟导入挪回模块顶层，本用例会立即失败。
    """
    assert fetcher.DataSourceUnavailableError is not None
    assert fetcher.SymbolNotFoundError is not None
    assert fetcher.PriceResult is not None


def test_submodules_share_the_same_exception_classes():
    """子模块与工厂必须引用同一批异常类，否则 CLI 的 except 捕不到。"""
    from holdings.data import a_stock, gold, us_stock

    assert a_stock.DataSourceUnavailableError is fetcher.DataSourceUnavailableError
    assert us_stock.SymbolNotFoundError is fetcher.SymbolNotFoundError
    assert gold.PriceResult is fetcher.PriceResult


@pytest.mark.parametrize(
    ("market", "expected"),
    [
        (MarketType.A_SHARE, AStockFetcher),
        (MarketType.US_STOCK, USStockFetcher),
        (MarketType.GOLD, GoldFetcher),
    ],
)
def test_get_fetcher_dispatches_by_market(market, expected):
    assert isinstance(fetcher.get_fetcher(market), expected)


def test_get_fetcher_rejects_unknown_market():
    with pytest.raises(fetcher.SymbolNotFoundError):
        fetcher.get_fetcher("不存在的市场")


def test_fetch_price_delegates_to_resolved_fetcher(monkeypatch):
    """fetch_price 应把请求交给 get_fetcher 选出的实例。"""
    calls = []

    class _Stub:
        def fetch(self, symbol):
            calls.append(symbol)
            return fetcher.PriceResult(symbol=symbol, price=1.23, source="stub")

    monkeypatch.setattr(fetcher, "get_fetcher", lambda market: _Stub())

    result = fetcher.fetch_price("600519", MarketType.A_SHARE)

    assert calls == ["600519"]
    assert result.price == 1.23
    assert result.source == "stub"


def test_afetch_price_wraps_sync_version(monkeypatch):
    """异步入口当前是同步垫片，应返回同样的结果。"""
    import asyncio

    monkeypatch.setattr(
        fetcher,
        "fetch_price",
        lambda symbol, market: fetcher.PriceResult(symbol=symbol, price=9.9),
    )

    result = asyncio.run(fetcher.afetch_price("AAPL", MarketType.US_STOCK))

    assert result.price == 9.9
