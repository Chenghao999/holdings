"""黄金行情（优先国内现货/黄金ETF，降级至国际黄金 GC=F）。"""

from __future__ import annotations

from holdings.data.fetcher import DataSourceUnavailableError, PriceResult, SymbolNotFoundError


class GoldFetcher:
    """黄金数据获取，优先国内现货，降级 yfinance 的 GC=F。"""

    def fetch(self, symbol: str) -> PriceResult:
        # 若指定为国内黄金ETF（如 518880），走 A 股行情
        if symbol not in ("", "GC=F"):
            from holdings.data.a_stock import AStockFetcher

            return AStockFetcher().fetch(symbol)
        return self._international_gold()

    def _international_gold(self) -> PriceResult:
        try:
            import yfinance as yf  # 懒加载
        except ImportError as exc:
            raise DataSourceUnavailableError("未安装 yfinance") from exc
        data = yf.Ticker("GC=F")
        hist = data.history(period="1d")
        if hist.empty:
            raise SymbolNotFoundError("未找到国际黄金 GC=F 行情")
        price = float(hist["Close"].iloc[-1])
        return PriceResult(symbol="GC=F", price=price, currency="USD", source="yfinance")