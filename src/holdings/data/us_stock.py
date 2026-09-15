"""美股行情：当前只有 yfinance 一个源。"""

from __future__ import annotations

from holdings.data import sources
from holdings.data.fetcher import DataSourceUnavailableError, PriceResult, SymbolNotFoundError
from holdings.models.enums import MarketType


class USStockFetcher:
    """美股数据获取。"""

    def fetch(self, symbol: str) -> PriceResult:
        return sources.fetch_with_fallback(
            symbol,
            MarketType.US_STOCK,
            {"yfinance": self._from_yfinance},
            f"美股数据源不可用：{symbol}",
        )

    def _from_yfinance(self, symbol: str) -> PriceResult:
        try:
            import yfinance as yf  # 懒加载
        except ImportError as exc:
            raise DataSourceUnavailableError("未安装 yfinance") from exc

        data = yf.Ticker(symbol)
        hist = data.history(period="1d")
        if hist.empty:
            raise SymbolNotFoundError(f"美股未找到标的：{symbol}")
        price = float(hist["Close"].iloc[-1])
        return PriceResult(symbol=symbol, price=price, currency="USD", source="yfinance")
