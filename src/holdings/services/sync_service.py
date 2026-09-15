"""价格同步服务：编排 data + storage，更新 price_cache。"""

from __future__ import annotations

from dataclasses import dataclass, field

from holdings.data import fetcher
from holdings.models.enums import MarketType
from holdings.storage import price_cache_dao, transaction_dao


@dataclass
class SyncResult:
    """同步结果对象。"""

    updated: list[dict] = field(default_factory=list)
    failed: list[dict] = field(default_factory=list)


def sync(db_path: str, market: MarketType, ttl_seconds: int = 300) -> SyncResult:
    """拉取最新价格并更新缓存。返回每个标的的成功/失败信息。"""
    transactions = transaction_dao.get_all(db_path)

    # 收集该市场下所有标的最新资产类型
    market_by_symbol: dict[str, MarketType] = {}
    for t in transactions:
        market_by_symbol[t.symbol] = t.market

    result = SyncResult()
    for symbol, symbol_market in market_by_symbol.items():
        if symbol_market != market:
            continue
        if price_cache_dao.is_fresh(db_path, symbol, ttl_seconds):
            continue
        try:
            price = fetcher.fetch_price(symbol, market)
            price_cache_dao.upsert(db_path, symbol, price.price, price.currency, price.source)
            result.updated.append({"symbol": symbol, "price": price.price, "source": price.source})
        except Exception as exc:
            result.failed.append({"symbol": symbol, "error": str(exc)})

    return result
