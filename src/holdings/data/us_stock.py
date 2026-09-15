"""美股行情（yfinance 实现）。"""

from __future__ import annotations

from holdings.data.fetcher import DataSourceUnavailableError, PriceResult, SymbolNotFoundError


class USStockFetcher:
    """美股数据获取。"""

    def fetch(self, symbol: str) -> PriceResult:
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
