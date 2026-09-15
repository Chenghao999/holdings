"""交易记录的 CRUD（Data Access Object）。

只负责读写数据，不做盈亏计算、不格式化输出。
"""

from __future__ import annotations

import sqlite3
from datetime import date

from holdings.models.enums import AssetType, MarketType, TradeType
from holdings.models.transaction import Transaction
from holdings.storage.db import DatabaseError, connect

_COLUMNS = (
    "portfolio_group",
    "symbol",
    "market",
    "asset_type",
    "trade_date",
    "trade_type",
    "quantity",
    "price",
    "fee",
    "notes",
)


def _row_to_transaction(row: sqlite3.Row) -> Transaction:
    return Transaction(
        id=row["id"],
        portfolio_group=row["portfolio_group"],
        symbol=row["symbol"],
        market=MarketType(row["market"]),
        asset_type=AssetType(row["asset_type"]),
        trade_date=date.fromisoformat(row["trade_date"]),
        trade_type=TradeType(row["trade_type"]),
        quantity=row["quantity"],
        price=row["price"],
        fee=row["fee"],
        notes=row["notes"],
    )


def add(db_path: str, tx: Transaction) -> int:
    """新增交易，返回自增 id。"""
    conn = connect(db_path)
    try:
        cur = conn.execute(
            f"INSERT INTO transactions ({', '.join(_COLUMNS)}) "
            f"VALUES ({', '.join('?' * len(_COLUMNS))})",
            (
                tx.portfolio_group,
                tx.symbol,
                tx.market.value,
                tx.asset_type.value,
                tx.trade_date.isoformat(),
                tx.trade_type.value,
                tx.quantity,
                tx.price,
                tx.fee,
                tx.notes,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)
    except sqlite3.Error as exc:
        raise DatabaseError(f"新增交易失败：{exc}") from exc
    finally:
        conn.close()


def get_all(db_path: str, group: str | None = None) -> list[Transaction]:
    """按 trade_date、id 升序返回全部交易（可筛选组合）。"""
    conn = connect(db_path)
    try:
        if group is not None:
            rows = conn.execute(
                "SELECT * FROM transactions WHERE portfolio_group = ? ORDER BY trade_date, id",
                (group,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM transactions ORDER BY trade_date, id").fetchall()
        return [_row_to_transaction(r) for r in rows]
    except sqlite3.Error as exc:
        raise DatabaseError(f"读取交易失败：{exc}") from exc
    finally:
        conn.close()


def get(db_path: str, transaction_id: int) -> Transaction | None:
    """按 id 返回单条交易，不存在返回 None。"""
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,)).fetchone()
        return _row_to_transaction(row) if row else None
    except sqlite3.Error as exc:
        raise DatabaseError(f"读取交易失败：{exc}") from exc
    finally:
        conn.close()


def remove(db_path: str, transaction_id: int) -> bool:
    """按 id 删除交易，返回是否删除成功。"""
    conn = connect(db_path)
    try:
        cur = conn.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
        conn.commit()
        return cur.rowcount > 0
    except sqlite3.Error as exc:
        raise DatabaseError(f"删除交易失败：{exc}") from exc
    finally:
        conn.close()


def symbols(db_path: str) -> list[str]:
    """返回出现过的所有标的代码（去重）。"""
    conn = connect(db_path)
    try:
        rows = conn.execute("SELECT DISTINCT symbol FROM transactions").fetchall()
        return [r["symbol"] for r in rows]
    except sqlite3.Error as exc:
        raise DatabaseError(f"读取标的失败：{exc}") from exc
    finally:
        conn.close()
