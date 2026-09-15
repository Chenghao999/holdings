"""data 层（fetcher 工厂与 A 股降级链路）的单元测试。

不触网也不等待：数据源全部打桩，`time.sleep` 一并打桩成 no-op，
只断言「调用了几次、走的哪条路」。
"""

import pytest

from holdings.data import fetcher, resilience
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


# ------------------------------------------------ A 股降级链路与 retry_count


@pytest.fixture
def a_stock(monkeypatch):
    """A 股 fetcher，且退避不真睡（否则每个用例白等 0.5 秒 × 重试次数）。"""
    from holdings.data import a_stock as module

    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    return AStockFetcher()


def _source(monkeypatch, fetcher_obj, attr, outcomes):
    """把某个数据源换成脚本化的假实现，返回调用记录。

    `outcomes` 按调用序号取；超出长度后一直用最后一项，方便写「一直失败」。
    """
    calls: list[str] = []

    def _fake(symbol):
        calls.append(symbol)
        outcome = outcomes[min(len(calls) - 1, len(outcomes) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(fetcher_obj, attr, _fake)
    return calls


def _ok(source: str = "akshare"):
    return fetcher.PriceResult(symbol="600519", price=1680.0, source=source)


@pytest.mark.parametrize("configured", [0, 1, 3])
def test_retry_count_controls_how_many_times_akshare_is_tried(
    a_stock, monkeypatch, configured
):
    """BACKLOG B-05 的判据：retry_count 改成几，就试几次（外加首次共 +1 次）。"""
    monkeypatch.setattr(resilience, "retry_count", lambda: configured)
    calls = _source(monkeypatch, a_stock, "_from_akshare", [RuntimeError("akshare 挂了")])
    _source(monkeypatch, a_stock, "_from_yfinance", [_ok("yfinance")])

    result = a_stock.fetch("600519")

    assert len(calls) == configured + 1
    assert result.source == "yfinance", "akshare 全部失败后应降级到 yfinance"


def test_akshare_success_does_not_call_yfinance(a_stock, monkeypatch):
    """一次成功就不该降级——降级是兜底，不是每次都走一遍。"""
    monkeypatch.setattr(resilience, "retry_count", lambda: 2)
    _source(monkeypatch, a_stock, "_from_akshare", [_ok("akshare")])
    yf_calls = _source(monkeypatch, a_stock, "_from_yfinance", [_ok("yfinance")])

    result = a_stock.fetch("600519")

    assert result.source == "akshare"
    assert yf_calls == []


def test_transient_failure_is_retried_without_falling_back(a_stock, monkeypatch):
    """失败一次后成功：不该降级，也不该把成功的结果丢掉。"""
    monkeypatch.setattr(resilience, "retry_count", lambda: 1)
    calls = _source(monkeypatch, a_stock, "_from_akshare", [RuntimeError("偶发"), _ok()])
    yf_calls = _source(monkeypatch, a_stock, "_from_yfinance", [_ok("yfinance")])

    result = a_stock.fetch("600519")

    assert len(calls) == 2
    assert result.source == "akshare"
    assert yf_calls == []


def test_both_sources_failing_raises_data_source_unavailable(a_stock, monkeypatch):
    """最终失败必须抛 DataSourceUnavailableError，而不是把原始异常漏出去。"""
    monkeypatch.setattr(resilience, "retry_count", lambda: 1)
    _source(monkeypatch, a_stock, "_from_akshare", [RuntimeError("akshare 挂了")])
    _source(monkeypatch, a_stock, "_from_yfinance", [RuntimeError("yfinance 也挂了")])

    with pytest.raises(fetcher.DataSourceUnavailableError) as exc:
        a_stock.fetch("600519")

    assert "600519" in str(exc.value)


def test_backoff_is_paid_once_per_retry_and_not_after_the_last_attempt(a_stock, monkeypatch):
    """退避只在「接下来还有一次尝试」时付出，失败收尾不该再白等一次。

    原先的写法把 sleep 放在 except 末尾，最后一次失败后仍要睡满才降级——
    用户多等半秒，什么也没等到。
    """
    from holdings.data import a_stock as module

    slept: list[float] = []
    monkeypatch.setattr(module.time, "sleep", slept.append)
    monkeypatch.setattr(resilience, "retry_count", lambda: 3)
    _source(monkeypatch, a_stock, "_from_akshare", [RuntimeError("一直失败")])
    _source(monkeypatch, a_stock, "_from_yfinance", [RuntimeError("也失败")])

    with pytest.raises(fetcher.DataSourceUnavailableError):
        a_stock.fetch("600519")

    assert slept == [module.RETRY_BACKOFF_SECONDS] * 3, "3 次重试 = 3 次退避，不多不少"


def test_retry_count_comes_from_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text(
        "sync:\n  retry_count: 3\n", encoding="utf-8"
    )

    assert resilience.retry_count() == 3


def test_retry_count_falls_back_when_the_config_is_unusable(tmp_path, monkeypatch):
    """配置坏了不该让取数据变成异常——如实报配置错误是别处的职责。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text("sync:\n  retry_count: 很多次\n", encoding="utf-8")

    assert resilience.retry_count() == resilience.DEFAULT_RETRY_COUNT
