"""data 层（fetcher 工厂与 A 股降级链路）的单元测试。

不触网也不等待：数据源全部打桩，`time.sleep` 一并打桩成 no-op，
只断言「调用了几次、走的哪条路」。
"""

import sys
import types

import pandas as pd
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
    """A 股 fetcher，且退避不真睡（否则每个用例白等 0.5 秒 × 重试次数）。

    退避与重试循环已收进 `data/sources.py`，所有市场共用，故打桩打在那里。
    """
    from holdings.data import sources

    monkeypatch.setattr(sources.time, "sleep", lambda _seconds: None)
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
def test_retry_count_controls_how_many_times_akshare_is_tried(a_stock, monkeypatch, configured):
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


def test_each_source_gets_its_own_retry_budget(a_stock, monkeypatch):
    """`retry_count` 是**每个源**的重试次数，不是整条链的总次数。

    akshare 用尽重试后，yfinance 也享有同样次数的机会——此前只有 akshare 会被
    重试、yfinance 一次失败即结束，那是硬编码降级链留下的偶然差异。
    """
    from holdings.data import sources as module

    retry_count = 3
    slept: list[float] = []
    monkeypatch.setattr(module.time, "sleep", slept.append)
    monkeypatch.setattr(resilience, "retry_count", lambda: retry_count)
    _source(monkeypatch, a_stock, "_from_akshare", [RuntimeError("一直失败")])
    _source(monkeypatch, a_stock, "_from_yfinance", [RuntimeError("也失败")])

    with pytest.raises(fetcher.DataSourceUnavailableError):
        a_stock.fetch("600519")

    assert slept == [module.RETRY_BACKOFF_SECONDS] * (retry_count * 2), (
        "两个源各退避 retry_count 次"
    )


def test_backoff_is_not_paid_after_the_last_attempt(a_stock, monkeypatch):
    """退避只在「接下来还有一次尝试」时付出，失败收尾不该再白等一次。

    原先的写法把 sleep 放在 except 末尾，最后一次失败后仍要睡满才降级——
    用户多等半秒，什么也没等到。
    """
    from holdings.data import sources as module

    slept: list[float] = []
    monkeypatch.setattr(module.time, "sleep", slept.append)
    monkeypatch.setattr(resilience, "retry_count", lambda: 2)
    # 只配 yfinance 一个源，退避次数就等于重试次数本身
    monkeypatch.setattr(module, "priority_for", lambda market: ["yfinance"])
    _source(monkeypatch, a_stock, "_from_yfinance", [RuntimeError("一直失败")])

    with pytest.raises(fetcher.DataSourceUnavailableError):
        a_stock.fetch("600519")

    assert slept == [module.RETRY_BACKOFF_SECONDS] * 2, "2 次重试 = 2 次退避，收尾不睡"


def test_retry_count_comes_from_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text("sync:\n  retry_count: 3\n", encoding="utf-8")

    assert resilience.retry_count() == 3


def test_retry_count_falls_back_when_the_config_is_unusable(tmp_path, monkeypatch):
    """配置坏了不该让取数据变成异常——如实报配置错误是别处的职责。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text("sync:\n  retry_count: 很多次\n", encoding="utf-8")

    assert resilience.retry_count() == resilience.DEFAULT_RETRY_COUNT


# ------------------------------------------------------- 数据源优先级配置


def test_priority_order_comes_from_config(a_stock, monkeypatch, tmp_path):
    """配置里把 yfinance 排在前面，就该先试 yfinance。"""
    from holdings.data import sources as module

    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text(
        "data_sources:\n  priority:\n    A股: [yfinance, akshare]\n", encoding="utf-8"
    )
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    akshare_calls = _source(monkeypatch, a_stock, "_from_akshare", [_ok("akshare")])
    yf_calls = _source(monkeypatch, a_stock, "_from_yfinance", [_ok("yfinance")])
    assert yf_calls is not None  # 两个源都替换掉，避免任何真联网的可能

    result = a_stock.fetch("600519")

    assert result.source == "yfinance"
    assert akshare_calls == [], "yfinance 已经成功了，不该再去碰 akshare"


def test_priority_falls_back_to_the_builtin_order_when_the_config_is_odd(tmp_path, monkeypatch):
    """配置写空列表是笔误，按内置顺序跑比整个同步失败有用。"""
    from holdings.data import sources as module

    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text(
        "data_sources:\n  priority:\n    A股: []\n", encoding="utf-8"
    )

    assert module.priority_for(MarketType.A_SHARE) == ["akshare", "yfinance"]


def test_unknown_source_names_are_skipped_rather_than_fatal(a_stock, monkeypatch, tmp_path):
    """配置里列了当前市场没有实现的源：跳过它，用剩下的那个。"""
    from holdings.data import sources as module

    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text(
        "data_sources:\n  priority:\n    A股: [sina, yfinance]\n", encoding="utf-8"
    )
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    yf_calls = _source(monkeypatch, a_stock, "_from_yfinance", [_ok("yfinance")])

    assert a_stock.fetch("600519").source == "yfinance"
    assert len(yf_calls) == 1


def test_a_market_with_no_usable_source_says_so(a_stock, monkeypatch, tmp_path):
    """一个都配不出来时明确指出，不让人对着「数据源不可用」猜。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text(
        "data_sources:\n  priority:\n    A股: [sina]\n", encoding="utf-8"
    )

    with pytest.raises(fetcher.DataSourceUnavailableError) as exc:
        a_stock.fetch("600519")

    assert "sina" in str(exc.value)


# ------------------------------------------------------------------ 黄金选路


def test_a_domestic_gold_symbol_never_gets_the_international_price(monkeypatch):
    """518880 拉不到价时应当失败，而不是拿 GC=F 的价格顶上。

    `sync_service` 按**请求的代码**入库（它不看 PriceResult.symbol），所以把
    国内链路失败回退到国际金价，等于把美元/盎司的报价存成一只人民币 ETF 的
    行情——数字差三个数量级，而且看不出来。
    """
    from holdings.data import sources
    from holdings.data.a_stock import AStockFetcher
    from holdings.data.gold import GoldFetcher

    # 两个源都会失败，重试的退避要打桩——否则这个用例真的睡满 1 秒。
    monkeypatch.setattr(sources.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        AStockFetcher,
        "_from_akshare",
        lambda self, symbol: (_ for _ in ()).throw(RuntimeError("挂了")),
    )
    monkeypatch.setattr(
        AStockFetcher,
        "_from_yfinance",
        lambda self, symbol: (_ for _ in ()).throw(RuntimeError("也挂了")),
    )
    international_calls: list[str] = []
    monkeypatch.setattr(
        GoldFetcher,
        "_international_gold",
        lambda self: (
            international_calls.append("GC=F")
            or fetcher.PriceResult(symbol="GC=F", price=2000.0, source="yfinance")
        ),
    )

    with pytest.raises(fetcher.DataSourceUnavailableError):
        GoldFetcher().fetch("518880")

    assert international_calls == [], "国内代码失败后绝不能去取国际金价顶上"


def test_the_international_symbol_goes_to_the_international_quote(monkeypatch):
    """`GC=F` 走国际金价；国内代码走 A 股链路——由代码选路，不靠配置。"""
    from holdings.data.gold import GoldFetcher

    monkeypatch.setattr(
        GoldFetcher,
        "_international_gold",
        lambda self, symbol: fetcher.PriceResult(symbol="GC=F", price=2000.0, source="yfinance"),
    )

    assert GoldFetcher().fetch("GC=F").price == 2000.0


# ------------------------------------------------ 各数据源的解析与懒加载分支


def _akshare_module(df):
    """伪造 akshare 模块：只提供 `_from_akshare` 用到的那一个函数。"""
    module = types.ModuleType("akshare")
    module.stock_zh_a_spot_em = lambda: df
    return module


def _yfinance_module(history, seen: list[str] | None = None):
    """伪造 yfinance 模块；`seen` 用来记录 Ticker 收到的代码（验后缀推导）。"""
    module = types.ModuleType("yfinance")

    class _Ticker:
        def __init__(self, symbol: str):
            if seen is not None:
                seen.append(symbol)

        def history(self, period: str):
            return history

    module.Ticker = _Ticker
    return module


def _spot(price: float):
    return pd.DataFrame({"代码": ["600519"], "最新价": [price]})


def _history(close: float):
    return pd.DataFrame({"Close": [close]})


def test_akshare_parses_the_latest_price(monkeypatch):
    monkeypatch.setitem(sys.modules, "akshare", _akshare_module(_spot(1680.5)))

    result = AStockFetcher()._from_akshare("600519")

    assert result.price == 1680.5
    assert result.currency == "CNY"
    assert result.source == "akshare"


def test_akshare_reports_a_missing_symbol(monkeypatch):
    monkeypatch.setitem(sys.modules, "akshare", _akshare_module(_spot(1680.5)))

    with pytest.raises(fetcher.SymbolNotFoundError):
        AStockFetcher()._from_akshare("000000")


def test_missing_akshare_raises_data_source_unavailable(monkeypatch):
    """懒加载：没装 akshare 时要报「未安装」，而不是漏一个 ImportError 出去。"""
    monkeypatch.setitem(sys.modules, "akshare", None)

    with pytest.raises(fetcher.DataSourceUnavailableError, match="akshare"):
        AStockFetcher()._from_akshare("600519")


@pytest.mark.parametrize(
    ("symbol", "expected"),
    [("600519", "600519.SS"), ("000001", "000001.SZ"), ("300750", "300750.SZ")],
)
def test_yfinance_appends_the_right_suffix(monkeypatch, symbol, expected):
    """上交所是 `.SS`、深交所是 `.SZ`——判据是 6 开头。

    推错后缀不会报错，只会查到一个不存在的代码然后「未找到标的」，
    排查起来毫无线索。
    """
    seen: list[str] = []
    monkeypatch.setitem(sys.modules, "yfinance", _yfinance_module(_history(10.0), seen))

    AStockFetcher()._from_yfinance(symbol)

    assert seen == [expected]


def test_yfinance_reports_a_missing_symbol(monkeypatch):
    monkeypatch.setitem(sys.modules, "yfinance", _yfinance_module(pd.DataFrame()))

    with pytest.raises(fetcher.SymbolNotFoundError):
        AStockFetcher()._from_yfinance("600519")


def test_missing_yfinance_raises_data_source_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "yfinance", None)

    with pytest.raises(fetcher.DataSourceUnavailableError, match="yfinance"):
        AStockFetcher()._from_yfinance("600519")


def test_us_stock_parses_the_close_price(monkeypatch):
    monkeypatch.setitem(sys.modules, "yfinance", _yfinance_module(_history(189.5)))

    result = USStockFetcher()._from_yfinance("AAPL")

    assert result.price == 189.5
    assert result.currency == "USD", "美股按美元计价"


def test_us_stock_reports_a_missing_symbol(monkeypatch):
    monkeypatch.setitem(sys.modules, "yfinance", _yfinance_module(pd.DataFrame()))

    with pytest.raises(fetcher.SymbolNotFoundError):
        USStockFetcher()._from_yfinance("NOPE")


def test_gold_uses_the_international_contract(monkeypatch):
    seen: list[str] = []
    monkeypatch.setitem(sys.modules, "yfinance", _yfinance_module(_history(2000.0), seen))

    result = GoldFetcher()._international_gold()

    assert seen == ["GC=F"], "国际金价走的是 GC=F 这个合约"
    assert result.symbol == "GC=F"
    assert result.currency == "USD"


def test_us_stock_without_yfinance_raises_data_source_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "yfinance", None)

    with pytest.raises(fetcher.DataSourceUnavailableError, match="yfinance"):
        USStockFetcher()._from_yfinance("AAPL")


def test_international_gold_without_yfinance_raises_data_source_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "yfinance", None)

    with pytest.raises(fetcher.DataSourceUnavailableError, match="yfinance"):
        GoldFetcher()._international_gold()


def test_a_domestic_gold_code_goes_through_the_a_share_path(monkeypatch):
    """国内代码（如 518880）交给 A 股链路，它自己有降级与重试。"""
    monkeypatch.setitem(sys.modules, "akshare", _akshare_module(_spot(4.85)))

    result = GoldFetcher().fetch("600519")

    assert result.source == "akshare", "走的是 A 股那条链，而不是国际金价"
