"""历史行情序列（B-39）：区间取数、清洗，以及 `--against` 的解析。

不触网：假 akshare / yfinance 模块**按真库的参数名与列名刻**。这不是形式——
B-36 就是 `GC=F` 的签名写错、次次失败，而那时用例全绿：降级链那句故意写宽的
`except Exception` 把 `TypeError` 吞成了「数据源不可用」，看起来像网络问题。
这里假源照真库定义，写错一个 kwarg 名字就会当场红。
"""

from __future__ import annotations

import sys
import types
from datetime import date

import pandas as pd
import pytest

from holdings.data import history, sources
from holdings.data.fetcher import DataSourceUnavailableError
from holdings.models.enums import MarketType


@pytest.fixture
def no_sleep(monkeypatch):
    """退避不真睡，否则每个失败用例白等 0.5 秒 × 重试次数。"""
    monkeypatch.setattr(sources.time, "sleep", lambda _seconds: None)


@pytest.fixture
def fake_akshare(monkeypatch):
    """装一个假的 akshare 模块，返回一个记录调用参数的容器。"""

    def _install(fn):
        module = types.ModuleType("akshare")
        module.index_zh_a_hist = fn
        monkeypatch.setitem(sys.modules, "akshare", module)

    return _install


# --------------------------------------------------------------- A 股：指数端点


def test_the_akshare_source_calls_the_real_signature_with_yyyymmdd(
    monkeypatch, fake_akshare, no_sleep
):
    """参数名按真库、日期传 `YYYYMMDD`（不是带横杠的 ISO）。

    `symbol` / `period` / `start_date` / `end_date` 四个名字与中文列名
    `日期` / `收盘` 都是从装的 akshare 1.18.96 源码里逐个抄下来的。
    假源照着定义，所以**签名对不上就是 `TypeError`**，不会静默通过。
    """
    seen: dict[str, object] = {}

    def index_zh_a_hist(symbol, period, start_date, end_date):
        seen.update(symbol=symbol, period=period, start_date=start_date, end_date=end_date)
        return pd.DataFrame({"日期": ["2024-01-02", "2024-01-03"], "收盘": [3000.0, 3060.0]})

    fake_akshare(index_zh_a_hist)

    got = history.fetch_history("000300", MarketType.A_SHARE, date(2024, 1, 1), date(2024, 1, 31))

    assert got.rows == [(date(2024, 1, 2), 3000.0), (date(2024, 1, 3), 3060.0)]
    # `source` 会写进 `price_history.source`：事后想弄清「这段数是谁给的」只有这里能回答。
    assert got.source == "akshare"
    assert seen == {
        "symbol": "000300",
        "period": "daily",
        "start_date": "20240101",
        "end_date": "20240131",
    }


def test_a_wrong_keyword_name_does_not_pass_silently(fake_akshare, no_sleep):
    """签名写错时必须**报出来**，而不是悄悄返回一个空序列。

    真库的参数名若与我们写的不符，假源（照真库定义）会 `TypeError`，
    降级链把它转成「数据源不可用」。这条用例钉的是「错误不会被吞成成功」。
    """

    def index_zh_a_hist(symbol, period, start, end):  # 真库叫 start_date / end_date
        raise AssertionError("不该被调用到")

    fake_akshare(index_zh_a_hist)

    with pytest.raises(DataSourceUnavailableError):
        history.fetch_history("000300", MarketType.A_SHARE, date(2024, 1, 1), date(2024, 1, 31))


def test_suspended_days_are_dropped_rather_than_zeroed(fake_akshare, no_sleep):
    """停牌 / 无成交那天收盘价是 `NaN`：跳过，不是当成 0。

    当成 0 会把那一段的收益率算成 −100%——一个看着像结论的错数。
    """

    def index_zh_a_hist(symbol, period, start_date, end_date):
        return pd.DataFrame(
            {"日期": ["2024-01-02", "2024-01-03", "2024-01-04"], "收盘": [3000.0, None, 3080.0]}
        )

    fake_akshare(index_zh_a_hist)

    got = history.fetch_history("000300", MarketType.A_SHARE, date(2024, 1, 1), date(2024, 1, 31))

    assert got.rows == [(date(2024, 1, 2), 3000.0), (date(2024, 1, 4), 3080.0)]


def test_the_series_comes_back_sorted_and_deduplicated(fake_akshare, no_sleep):
    """乱序 + 重复的日子：升序输出、同日只留一条，下游才能按序二分对齐。"""

    def index_zh_a_hist(symbol, period, start_date, end_date):
        return pd.DataFrame(
            {"日期": ["2024-01-04", "2024-01-02", "2024-01-02"], "收盘": [3080.0, 2990.0, 3000.0]}
        )

    fake_akshare(index_zh_a_hist)

    got = history.fetch_history("000300", MarketType.A_SHARE, date(2024, 1, 1), date(2024, 1, 31))

    assert got.rows == [(date(2024, 1, 2), 3000.0), (date(2024, 1, 4), 3080.0)]


def test_an_empty_result_is_a_failure_not_an_empty_series(fake_akshare, no_sleep):
    """空 DataFrame 不抛异常，必须显式判成失败——否则降级链收到的是「成功」。"""

    def index_zh_a_hist(symbol, period, start_date, end_date):
        return pd.DataFrame({"日期": [], "收盘": []})

    fake_akshare(index_zh_a_hist)

    with pytest.raises(DataSourceUnavailableError):
        history.fetch_history("000300", MarketType.A_SHARE, date(2024, 1, 1), date(2024, 1, 31))


def test_missing_akshare_is_reported_as_a_data_source_problem(monkeypatch, no_sleep):
    """没装 akshare 时是 `MissingDependency` 之外的「取不到」，走同一个退出码 1。

    `sys.modules[name] = None` 会让 `import name` 抛 `ImportError`，这正是
    「没装这个包」在运行时的样子。
    """
    monkeypatch.setitem(sys.modules, "akshare", None)

    with pytest.raises(DataSourceUnavailableError):
        history.fetch_history("000300", MarketType.A_SHARE, date(2024, 1, 1), date(2024, 1, 31))


# ----------------------------------------------------------------- 美股：yfinance


def test_yfinance_gets_an_exclusive_end_one_day_later(monkeypatch, no_sleep):
    """yfinance 的 `end` 是**开区间**：不 +1 天，最后一条快照那天会静默缺席。

    序列短一天不会报错，只会让算出来的收益少一段——正是这种「看着正常」
    才要一条用例钉住。
    """
    seen: dict[str, object] = {}

    class _Ticker:
        def __init__(self, symbol):
            seen["symbol"] = symbol

        def history(self, start, end):
            seen["start"], seen["end"] = start, end
            index = pd.DatetimeIndex(["2024-01-02", "2024-01-03"], tz="America/New_York")
            return pd.DataFrame({"Close": [4700.0, 4720.0]}, index=index)

    module = types.ModuleType("yfinance")
    module.Ticker = _Ticker
    monkeypatch.setitem(sys.modules, "yfinance", module)

    got = history.fetch_history("^GSPC", MarketType.US_STOCK, date(2024, 1, 1), date(2024, 1, 31))

    assert seen == {"symbol": "^GSPC", "start": date(2024, 1, 1), "end": date(2024, 2, 1)}
    # 带时区的 Timestamp 取交易所那一天，不是 UTC 那天。
    assert got.rows == [(date(2024, 1, 2), 4700.0), (date(2024, 1, 3), 4720.0)]
    assert got.source == "yfinance"


def test_a_market_without_a_history_source_says_so(no_sleep):
    """黄金没有历史源：明确说「暂不支持」，而不是让 `KeyError` 冒到用户脸上。"""
    with pytest.raises(DataSourceUnavailableError, match="暂不支持"):
        history.fetch_history("GC=F", MarketType.GOLD, date(2024, 1, 1), date(2024, 1, 31))


# ------------------------------------------------------------------ --against 解析


@pytest.mark.parametrize(
    ("text", "symbol", "market"),
    [
        ("沪深300", "000300", MarketType.A_SHARE),
        ("中证500", "000905", MarketType.A_SHARE),
        ("上证指数", "000001", MarketType.A_SHARE),
        ("标普500", "^GSPC", MarketType.US_STOCK),
        ("纳斯达克", "^IXIC", MarketType.US_STOCK),
        ("399001", "399001", MarketType.A_SHARE),
        ("^HSI", "^HSI", MarketType.US_STOCK),
        ("SPY", "SPY", MarketType.US_STOCK),
        ("  000300  ", "000300", MarketType.A_SHARE),
    ],
)
def test_resolving_a_benchmark(text, symbol, market):
    ref = history.resolve_against(text)

    assert ref is not None
    assert (ref.symbol, ref.market) == (symbol, market)


def test_the_alias_label_shows_both_the_name_and_the_code():
    """回显带代码：`沪深300` 与 `000300` 是同一个东西，说清楚省得用户再查。"""
    assert history.resolve_against("沪深300").label == "沪深300（000300）"


@pytest.mark.parametrize("text", ["乱写的", "hushen300", "600519.SS", "^", "", "   "])
def test_an_unrecognized_benchmark_resolves_to_nothing(text):
    """认不出就是 `None`，由调用方报出来。

    **不退化成"随便挑一个市场去问"**：`instrument.market_candidates` 对任何
    字符串都返回一个市场，照着它走会把「认不出这是哪个市场的基准」混成
    「网络取不到」，用户照着错的方向去查网络、重装依赖（B-36 是同一类）。
    """
    assert history.resolve_against(text) is None


def test_the_alias_table_points_at_indexes():
    """⚠️ 别名表里的代码走的是**指数**端点：`000001` 是上证指数、不是平安银行。

    这条用例把这张表钉住——它最容易在「顺手加一个常用指数」时被填成个股代码。
    """
    assert history.BENCHMARK_ALIASES["上证指数"] == ("000001", MarketType.A_SHARE)
    assert history.BENCHMARK_ALIASES["沪深300"] == ("000300", MarketType.A_SHARE)


def test_a_missing_yfinance_is_reported_as_a_data_source_problem(monkeypatch, no_sleep):
    monkeypatch.setitem(sys.modules, "yfinance", None)

    with pytest.raises(DataSourceUnavailableError):
        history.fetch_history("^GSPC", MarketType.US_STOCK, date(2024, 1, 1), date(2024, 1, 31))


def test_an_empty_yfinance_frame_is_a_failure_too(monkeypatch, no_sleep):
    """`Ticker.history` 取不到东西时返回**空 DataFrame 而不抛异常**。

    不显式判成失败，降级链收到的是「成功」——一个空序列会一路走到对齐那一步，
    最后的表现是「找不到收盘价」，与真正的原因（这个代码取不到）隔了好几层。
    """

    class _Ticker:
        def __init__(self, symbol):
            pass

        def history(self, start, end):
            return pd.DataFrame({"Close": []})

    module = types.ModuleType("yfinance")
    module.Ticker = _Ticker
    monkeypatch.setitem(sys.modules, "yfinance", module)

    with pytest.raises(DataSourceUnavailableError):
        history.fetch_history("^GSPC", MarketType.US_STOCK, date(2024, 1, 1), date(2024, 1, 31))


def test_a_plain_date_column_is_accepted_as_well(fake_akshare, no_sleep):
    """akshare 回的日期类型不止一种（字符串 / `date` / `Timestamp`），都要能收。

    真实取数里见过字符串；`date` 与 `Timestamp` 是它的另两种可能形态，
    统一在 `_clean` 里做，免得下游按日期排序时踩到混着类型的列表。
    """

    def index_zh_a_hist(symbol, period, start_date, end_date):
        return pd.DataFrame(
            {"日期": [date(2024, 1, 3), date(2024, 1, 2)], "收盘": [3060.0, 3000.0]}
        )

    fake_akshare(index_zh_a_hist)

    got = history.fetch_history("000300", MarketType.A_SHARE, date(2024, 1, 1), date(2024, 1, 31))

    assert got.rows == [(date(2024, 1, 2), 3000.0), (date(2024, 1, 3), 3060.0)]


def test_the_history_source_order_ignores_the_price_priority(
    tmp_path, monkeypatch, fake_akshare, no_sleep
):
    """历史序列的源顺序**显式写死**，不读 `data_sources.priority`（B-05 的教训）。

    用户为**取价**把 A 股改成只留 `yfinance` 是完全合理的操作；而 A 股历史这里
    只有 akshare 一个源。跟着取价走的话，那个源会被「配置里没写」滤掉，基准
    功能被一个**无关的**配置项悄悄关掉——而报出来的是「数据源都不可用」。

    所以这条用例故意把 A 股的取价优先级设成 `yfinance`，再确认历史照样取得到。
    """
    (tmp_path / "config.yaml").write_text(
        "data_sources:\n  priority:\n    A股: [yfinance]\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    def index_zh_a_hist(symbol, period, start_date, end_date):
        return pd.DataFrame({"日期": ["2024-01-02"], "收盘": [3000.0]})

    fake_akshare(index_zh_a_hist)

    got = history.fetch_history("000300", MarketType.A_SHARE, date(2024, 1, 1), date(2024, 1, 31))

    assert got.rows == [(date(2024, 1, 2), 3000.0)]
