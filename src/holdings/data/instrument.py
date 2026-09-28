"""标的资料：名称、市场、资产类型、币种的获取。

`PriceResult` 只有代码、价格、币种、来源——「这个代码是什么」在真实使用中问的是
**名称、市场、资产类型**。`asset_meta` 表早就有这几个字段，但此前除手工
`holdings meta` 之外没有任何东西能把它们填上，于是「股票信息」实际只有价格。

降级用的是**取价那同一套** `sources.fetch_with_fallback`：按配置顺序逐个试、
各自带 `sync.retry_count` 次重试、配了但这里没有的源跳过。不再写第二套的理由
不只是省代码——两套降级迟早会在重试次数、退避、异常范围上悄悄分叉，而用户
只会觉得「取价能用、取名字不能用」是玄学。

**加一个新来源 = 在 `_SOURCES` 里加一个函数 + 配置里加一个名字**，降级逻辑
一行都不用动。
"""

from __future__ import annotations

from dataclasses import dataclass

from holdings.data import sources
from holdings.data.fetcher import DataSourceUnavailableError, SymbolNotFoundError
from holdings.models.enums import AssetType, MarketType


@dataclass
class SymbolInfo:
    """一个标的的「是什么」。

    `name` 与 `asset_type` 允许为 None：**不是每个源都知道每一件事**。不知道就
    如实留空，而不是拿代码前缀猜一个——猜错的资产类型会一路走进报表，而用户
    没有任何办法看出它是猜的。
    """

    symbol: str
    name: str | None = None
    market: MarketType | None = None
    asset_type: AssetType | None = None
    currency: str = "CNY"
    #: 这条资料是哪个源给的（`akshare` / `yfinance`），与 `PriceResult.source` 同义。
    source: str = ""


def fetch_instrument(symbol: str, market: MarketType) -> SymbolInfo:
    """按市场取一个标的的资料。

    A 股与美股各有自己的源表；**黄金不在此列**——它的两个「源」是两种不同的
    标的（国内 ETF 与 GC=F 合约），不是彼此的备份，理由与 `gold.py` 里写的
    完全一样。国内黄金代码走 A 股链路照样能取到名字。
    """
    market_sources = _SOURCES.get(market)
    if not market_sources:
        raise DataSourceUnavailableError(f"{market.value}暂不支持获取标的资料：{symbol}")
    return sources.fetch_with_fallback(
        symbol,
        market,
        market_sources,
        f"{market.value}标的资料不可用：{symbol}",
        key=sources.INSTRUMENT_PRIORITY_KEY,
    )


def _a_share_from_akshare(symbol: str) -> SymbolInfo:
    try:
        import akshare as ak  # 懒加载
    except ImportError as exc:
        raise DataSourceUnavailableError("未安装 akshare") from exc
    df = ak.stock_zh_a_spot_em()
    row = df[df["代码"] == symbol]
    if row.empty:
        # ETF / LOF 不在这张表里（那是 `fund_etf_spot_em` 的地盘），抛出后由
        # 降级链交给 yfinance——它认得 `quoteType`，正好补上资产类型。
        raise SymbolNotFoundError(f"akshare 未找到 A股标的：{symbol}")
    return SymbolInfo(
        symbol=symbol,
        name=str(row.iloc[0]["名称"]),
        market=MarketType.A_SHARE,
        # 这张表只有个股，所以「在这里找到了」本身就说明了资产类型。
        asset_type=AssetType.STOCK,
        currency="CNY",
        source="akshare",
    )


def _a_share_from_yfinance(symbol: str) -> SymbolInfo:
    # A 股代码在 yfinance 里带交易所后缀，与 `a_stock.py` 的取价逻辑同一套规则。
    suffix = ".SS" if symbol.startswith("6") else ".SZ"
    return _from_yfinance(symbol, f"{symbol}{suffix}", MarketType.A_SHARE, "CNY")


def _us_from_yfinance(symbol: str) -> SymbolInfo:
    return _from_yfinance(symbol, symbol, MarketType.US_STOCK, "USD")


def _from_yfinance(
    symbol: str, ticker_name: str, market: MarketType, default_currency: str
) -> SymbolInfo:
    """yfinance 的 `info` 是三个市场共用的解析：查得到什么就填什么。"""
    try:
        import yfinance as yf  # 懒加载
    except ImportError as exc:
        raise DataSourceUnavailableError("未安装 yfinance") from exc

    info = yf.Ticker(ticker_name).info or {}
    # 名字给得不一致：`shortName` 常见于美股，`longName` 更全，两者都没有才算没查到。
    name = info.get("shortName") or info.get("longName")
    if not name:
        raise SymbolNotFoundError(f"yfinance 未找到标的资料：{ticker_name}")
    return SymbolInfo(
        symbol=symbol,
        name=str(name),
        market=market,
        asset_type=_ASSET_TYPES.get(str(info.get("quoteType", "")).upper()),
        currency=str(info.get("currency") or default_currency),
        source="yfinance",
    )


#: yfinance 的 `quoteType` 取值 → 本工具的资产类型。
#: 认不出的（指数、货币、期货……）留空，不硬塞成 `stock`。
_ASSET_TYPES: dict[str, AssetType] = {
    "EQUITY": AssetType.STOCK,
    "ETF": AssetType.ETF,
}

#: 市场 → 该市场**实现得出来**的标的资料来源。顺序由配置的
#: `data_sources.instrument_priority` 决定，这里只声明「有哪些」。
_SOURCES: dict[MarketType, dict[str, sources.Source[SymbolInfo]]] = {
    MarketType.A_SHARE: {
        "akshare": _a_share_from_akshare,
        "yfinance": _a_share_from_yfinance,
    },
    MarketType.US_STOCK: {"yfinance": _us_from_yfinance},
}
