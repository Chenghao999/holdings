"""黄金行情：按代码选路——国内现货/黄金 ETF 走 A 股链路，`GC=F` 走国际金价。

**这个市场不参与 `data_sources.priority`。** 它的两个源是两种不同的标的，
不是彼此的备份：把「国内 518880」失败后回退到「国际 GC=F」，`sync_service`
会把 GC=F 的价格（美元/盎司，约 2000）按**请求的代码**存进 `price_cache`，
于是 518880 的行情位置上躺着一只 ETF 永远不可能有的价格。
代码是 `GC=F` 还是国内代码，用户已经说得很清楚，不需要配置再替他决定。
"""

from __future__ import annotations

from holdings.data import sources
from holdings.data.fetcher import DataSourceUnavailableError, PriceResult, SymbolNotFoundError
from holdings.models.enums import MarketType

#: 走国内链路时认不出来的代码——它们表示「要的是国际金价」。
_INTERNATIONAL_SYMBOLS = ("", "GC=F")


class GoldFetcher:
    """黄金数据获取。"""

    def fetch(self, symbol: str) -> PriceResult:
        if symbol in _INTERNATIONAL_SYMBOLS:
            # 只此一个源，同样过一遍重试循环，好让重试行为在所有市场一致。
            return sources.fetch_with_fallback(
                symbol,
                MarketType.GOLD,
                {"yfinance": self._international_gold},
                f"国际黄金数据源不可用：{symbol or 'GC=F'}",
                order=["yfinance"],
            )
        # 国内代码：交给 A 股那条链路（它自己有 akshare → yfinance 的降级与重试）
        from holdings.data.a_stock import AStockFetcher

        return AStockFetcher().fetch(symbol)

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
