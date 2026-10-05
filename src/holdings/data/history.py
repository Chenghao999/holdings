"""历史行情序列：一段区间内的收盘价（B-39）。

取价那条链路（`markets.FETCHERS` + 三个 fetcher）**只有「最新价」**：
`price_cache` 一个代码一行，每个 fetcher 都只返回当下一刻。基准对比要的是一段
**序列**，形状根本不同，所以这里自带一张源表，而不是给 fetcher 加个参数——
分工与 `instrument.py` 自带源表完全一样。

**这里只取指数。** A 股走 `ak.index_zh_a_hist`（指数端点），所以 `000001`
在这个文件里是**上证指数**、不是平安银行；个股与 ETF 不服务。美股走 yfinance，
指数与个股都行（见模块末的取舍说明）。

降级用的是取价那同一套 `sources.fetch_with_fallback`，但顺序**显式写死**，
不读 `data_sources.priority`——理由见 `fetch_history` 的说明。
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from holdings.data import sources
from holdings.data.fetcher import DataSourceUnavailableError, SymbolNotFoundError
from holdings.models.enums import MarketType

#: 一段历史：按交易日升序的 `(日期, 收盘价)`。
History = list[tuple[date, float]]

#: A 股指数代码的形状：6 位数字。与 `instrument.py` 判 A 股代码是同一条规则，
#: 但两边用途不同——那边决定「先问哪个市场」，这里决定「这个写法像不像基准」。
_A_SHARE_CODE = re.compile(r"\d{6}")

#: 美股代码的形状：`^` 开头的指数（`^GSPC`），或大写字母开头的个股 / ETF
#: （`AAPL`、`BRK-B`、`SPY`）。**要求大写开头**是故意的：这条判据的意义在于
#: 把「认不出的写法」挡在门外（否则一个错别字会以「网络取不到」的面目出现），
#: 而小写的 `aapl` 与拼音 `hushen300` 分不出来——宁可让用户把代码改成大写，
#: 也不要让「我不认识这个词」混成「网络有问题」。
_US_CODE = re.compile(r"\^[A-Za-z0-9.=\-]+|[A-Z][A-Z0-9.\-]*")

#: 常用基准的别名 → `(代码, 市场)`。
#:
#: ⚠️ **这些代码走的是指数端点**：`000001` 是**上证指数**，不是平安银行；
#: `000300` 是沪深 300，不是某只个股。同一个 6 位数字在个股端点下是另一条
#: 完全不同的价格序列——这是整个文件最容易看错的一处，所以别名表紧挨着源表放，
#: 而不是散到命令层去。
BENCHMARK_ALIASES: dict[str, tuple[str, MarketType]] = {
    "沪深300": ("000300", MarketType.A_SHARE),
    "中证500": ("000905", MarketType.A_SHARE),
    "上证指数": ("000001", MarketType.A_SHARE),
    "标普500": ("^GSPC", MarketType.US_STOCK),
    "纳斯达克": ("^IXIC", MarketType.US_STOCK),
}


@dataclass(frozen=True)
class BenchmarkRef:
    """`--against` 解析出来的东西：去问哪个代码、算哪个市场、显示成什么。"""

    symbol: str
    market: MarketType
    #: 给人看的写法，如 `沪深300（000300）`。
    label: str


def resolve_against(text: str) -> BenchmarkRef | None:
    """把 `--against` 的取值解析成 `BenchmarkRef`；认不出时返回 `None`。

    先查别名表；否则按**代码形状**判市场——6 位数字是 A 股指数，
    美股代码的形状见 `_US_CODE`（`^` 开头的指数，或大写字母开头的个股 / ETF）。
    两条都不像就是认不出，由调用方报出来。

    **不要退化成"随便挑一个市场去问"**：那会把一句「认不出这是哪个市场的基准」
    混成「网络取不到」，用户照着错的方向去查网络、重装依赖，而问题在自己敲的
    那个词上（B-36 是同一类：真因被吞成「数据源不可用」）。
    """
    key = text.strip()
    if key in BENCHMARK_ALIASES:
        symbol, market = BENCHMARK_ALIASES[key]
        return BenchmarkRef(symbol=symbol, market=market, label=f"{key}（{symbol}）")
    if _A_SHARE_CODE.fullmatch(key):
        return BenchmarkRef(symbol=key, market=MarketType.A_SHARE, label=key)
    if _US_CODE.fullmatch(key):
        return BenchmarkRef(symbol=key, market=MarketType.US_STOCK, label=key)
    return None


def history_sources(start: date, end: date) -> dict[MarketType, dict[str, sources.Source[History]]]:
    """按取数区间造一份源表。

    闭包把 `start` / `end` 绑进源里，保住 `source(symbol)` 这个**一参形状**——
    降级链就是按 `source(symbol)` 调的，而它那句 `except Exception` 是故意写宽的：
    签名对不上时，报出来的不是「我这段代码写错了」，而是「数据源不可用」
    （B-36：`GC=F` 就这么坏了整个 v1）。`tests/test_data.py` 有一条守卫钉着形状。
    """
    return {
        MarketType.A_SHARE: {"akshare": _a_share_history(start, end)},
        MarketType.US_STOCK: {"yfinance": _us_history(start, end)},
    }


def fetch_history(symbol: str, market: MarketType, start: date, end: date) -> History:
    """取一段历史收盘价，按交易日升序、同一天只留一条。

    `order` **显式写死，不走 `data_sources.priority`**：那是给**取价**用的顺序，
    用户为取价把 A 股改成 `["yfinance"]` 是完全合理的操作，而历史序列这边 A 股
    只有 akshare 一个源——跟着取价走的话，那个源会被「配置里没写」滤掉，
    基准功能被一个无关的配置项悄悄关掉（B-05 删掉的那类「一个配置管了另一件事」）。
    真有第二个历史源时再加 `history_priority` 也不迟。
    """
    market_sources = history_sources(start, end).get(market)
    if not market_sources:
        raise DataSourceUnavailableError(f"{market.value}暂不支持历史行情：{symbol}")
    order = ["akshare"] if market is MarketType.A_SHARE else ["yfinance"]
    return sources.fetch_with_fallback(
        symbol,
        market,
        market_sources,
        f"{market.value}历史行情不可用：{symbol}",
        order=order,
    )


def _a_share_history(start: date, end: date) -> sources.Source[History]:
    def _source(symbol: str) -> History:
        try:
            import akshare as ak  # 懒加载
        except ImportError as exc:
            raise DataSourceUnavailableError("未安装 akshare") from exc
        # `index_zh_a_hist` 的日期参数是 **`YYYYMMDD` 字符串**（不是带横杠的 ISO），
        # 返回的是**中文列名** `日期` / `收盘`。签名与列名都在本机装的
        # akshare 1.18.96 源码里逐个核对过——B-36 就是「签名写错、次次失败」
        # 而用例全绿才漏过去的。
        df = ak.index_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
        )
        if df is None or df.empty:
            raise SymbolNotFoundError(f"akshare 未找到 A股指数历史行情：{symbol}")
        return _clean(df["日期"], df["收盘"])

    return _source


def _us_history(start: date, end: date) -> sources.Source[History]:
    def _source(symbol: str) -> History:
        try:
            import yfinance as yf  # 懒加载
        except ImportError as exc:
            raise DataSourceUnavailableError("未安装 yfinance") from exc
        # **`end` 是开区间**：yfinance 的 `history` 文档写着 exclusive，传末条
        # 快照当天会让最后一天**静默缺席**（序列短一天，算出来的数看着正常）。
        # 所以这里 +1 天。
        hist = yf.Ticker(symbol).history(start=start, end=end + timedelta(days=1))
        # 空 DataFrame 不抛异常（`raise_errors` 默认为 False）：不显式判成失败，
        # 降级链就收不到信号，会把「什么都没取到」当成一次成功的取数。
        if hist is None or hist.empty:
            raise SymbolNotFoundError(f"yfinance 未找到历史行情：{symbol}")
        return _clean(hist.index, hist["Close"])

    return _source


def _clean(dates: Sequence, closes: Sequence) -> History:
    """一对「日期列 / 收盘价列」→ 升序、同一天只留一条的序列。

    两个源回的日期类型不一样（akshare 是 `datetime.date` 或字符串，yfinance 是
    带时区的 `Timestamp`），在这里统一成 `date`；停牌 / 无成交的那些日子收盘价是
    `NaN`，**跳过而不是当成 0**——0 会把那一段的收益率算成 −100%。
    重复的日子留后一条，免得下游按「严格升序」做二分查找时踩到重复键。
    """
    merged: dict[date, float] = {}
    for raw_date, raw_close in zip(dates, closes, strict=True):
        close = float(raw_close)
        if math.isnan(close):
            continue
        merged[_to_date(raw_date)] = close
    return sorted(merged.items())


def _to_date(value) -> date:
    """各种日期表示 → `date`。`Timestamp` 是 `datetime` 的子类，先被它接住。"""
    if isinstance(value, datetime):
        # 带时区的 Timestamp 取它自己时区下的那一天，也就是交易所的那个交易日。
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])
