"""A 股行情：默认可选 akshare，失败降级 yfinance。

降级顺序不写死在这里，由 `data_sources.priority` 决定（见 `data/sources.py`）。
"""

from __future__ import annotations

from holdings.data import sources
from holdings.data.fetcher import DataSourceUnavailableError, PriceResult
from holdings.models.enums import MarketType


class AStockFetcher:
    """A 股数据获取。"""

    def fetch(self, symbol: str) -> PriceResult:
        return sources.fetch_with_fallback(
            symbol,
            MarketType.A_SHARE,
            {"akshare": self._from_akshare, "yfinance": self._from_yfinance},
            f"A股数据源不可用：{symbol}",
        )

    def _from_akshare(self, symbol: str) -> PriceResult:
        try:
            import akshare as ak  # 懒加载
        except ImportError as exc:
            raise DataSourceUnavailableError("未安装 akshare") from exc
        # 东财实时行情接口，返回 DataFrame（列：代码、名称、最新价等）
        df = ak.stock_zh_a_spot_em()
        row = df[df["代码"] == symbol]
        if row.empty:
            from holdings.data.fetcher import SymbolNotFoundError

            raise SymbolNotFoundError(f"A股未找到标的：{symbol}")
        price = float(row.iloc[0]["最新价"])
        return PriceResult(symbol=symbol, price=price, currency="CNY", source="akshare")

    def _from_yfinance(self, symbol: str) -> PriceResult:
        try:
            import yfinance as yf  # 懒加载
        except ImportError as exc:
            raise DataSourceUnavailableError("未安装 yfinance") from exc
        # yfinance 中 A 股代码带后缀，如 600519.SS
        suffix = ".SS" if symbol.startswith("6") else ".SZ"
        data = yf.Ticker(f"{symbol}{suffix}")
        hist = data.history(period="1d")
        if hist.empty:
            from holdings.data.fetcher import SymbolNotFoundError

            raise SymbolNotFoundError(f"yfinance 未找到 A股标的：{symbol}")
        price = float(hist["Close"].iloc[-1])
        return PriceResult(symbol=symbol, price=price, currency="CNY", source="yfinance")
