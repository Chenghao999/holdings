"""价格缓存的读写。"""

from __future__ import annotations

import sqlite3

from holdings.storage import db
from holdings.storage.db import DatabaseError, connect


class CachedPrice:
    def __init__(self, symbol: str, price: float, currency: str, update_time: str, source: str):
        self.symbol = symbol
        self.price = price
        self.currency = currency
        self.update_time = update_time
        self.source = source


def get(db_path: str, symbol: str) -> CachedPrice | None:
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT * FROM price_cache WHERE symbol = ?", (symbol,)).fetchone()
        if not row:
            return None
        return CachedPrice(
            symbol=row["symbol"],
            price=row["price"],
            currency=row["currency"],
            update_time=row["update_time"],
            source=row["source"] or "",
        )
    except sqlite3.Error as exc:
        raise DatabaseError(f"读取价格缓存失败：{exc}") from exc
    finally:
        conn.close()


def upsert(
    db_path: str,
    symbol: str,
    price: float,
    currency: str = "CNY",
    source: str = "",
) -> None:
    conn = connect(db_path)
    try:
        conn.execute(
            "INSERT INTO price_cache (symbol, price, currency, update_time, source) "
            "VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?) "
            "ON CONFLICT(symbol) DO UPDATE SET "
            "price=excluded.price, currency=excluded.currency, "
            "update_time=CURRENT_TIMESTAMP, source=excluded.source",
            (symbol, price, currency, source),
        )
        conn.commit()
    except sqlite3.Error as exc:
        raise DatabaseError(f"写入价格缓存失败：{exc}") from exc
    finally:
        conn.close()


def is_fresh(db_path: str, symbol: str, ttl_seconds: int) -> bool:
    """判断缓存是否在 ttl 秒内更新过。"""
    cached = get(db_path, symbol)
    if cached is None:
        return False
    return db.timestamp_is_fresh(cached.update_time, ttl_seconds)
