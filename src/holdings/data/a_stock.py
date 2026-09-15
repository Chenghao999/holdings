"""A 股行情（akshare 实现，降级至 yfinance，含超时重试）。"""

from __future__ import annotations

import time

from holdings.data.fetcher import DataSourceUnavailableError, PriceResult


class AStockFetcher:
    """A 股数据获取，优先 akshare，降级 yfinance。"""

    def fetch(self, symbol: str) -> PriceResult:
        return self._with_fallback(symbol)

    def _with_fallback(self, symbol: str) -> PriceResult:
        last_err: Exception | None = None
        for _ in range(2):  # 超时重试 1 次
            # 重试循环的 try 必须在循环体内，PERF203 在此不适用。
            try:
                return self._from_akshare(symbol)
            except Exception as exc:  # noqa: PERF203 - 降级捕获所有异常
                last_err = exc
                time.sleep(0.5)
        # 降级至 yfinance（仅支持部分 A 股大盘）
        try:
            return self._from_yfinance(symbol)
        except Exception as exc:  # 降级捕获所有异常
            last_err = exc
        raise DataSourceUnavailableError(f"A股数据源不可用：{symbol}") from last_err

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
