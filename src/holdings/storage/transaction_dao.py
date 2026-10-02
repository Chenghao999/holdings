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
    "source",
    "external_id",
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
        source=row["source"],
        external_id=row["external_id"],
    )


_INSERT_SQL = (
    f"INSERT INTO transactions ({', '.join(_COLUMNS)}) VALUES ({', '.join('?' * len(_COLUMNS))})"
)


def _to_params(tx: Transaction) -> tuple:
    return (
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
        tx.source,
        tx.external_id,
    )


def add(db_path: str, tx: Transaction) -> int:
    """新增交易，返回自增 id。"""
    conn = connect(db_path)
    try:
        cur = conn.execute(_INSERT_SQL, _to_params(tx))
        conn.commit()
        return int(cur.lastrowid)
    except sqlite3.Error as exc:
        raise DatabaseError(f"新增交易失败：{exc}") from exc
    finally:
        conn.close()


def add_many(db_path: str, txs: list[Transaction]) -> list[int]:
    """在同一个事务内批量新增交易，返回自增 id 列表。

    任一条失败则整批回滚：CSV 导入依赖这个语义，否则中途报错会留下一半数据。
    """
    if not txs:
        return []
    conn = connect(db_path)
    ids: list[int] = []
    try:
        for tx in txs:
            cur = conn.execute(_INSERT_SQL, _to_params(tx))
            ids.append(int(cur.lastrowid))
        conn.commit()
        return ids
    except sqlite3.Error as exc:
        conn.rollback()
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


def list_groups(db_path: str) -> list[str]:
    """返回交易里出现过的所有组合名（去重、名称升序）。

    排除 NULL：建表时 `portfolio_group` 只是 `DEFAULT '默认'` 而没有 NOT NULL，
    老库或手工插入的行可能是 NULL。把 `None` 当组合名返回出去，调用方拿它去
    筛交易会得到一条空结果，看起来像「有个叫 None 的空组合」。
    """
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT DISTINCT portfolio_group FROM transactions "
            "WHERE portfolio_group IS NOT NULL ORDER BY portfolio_group"
        ).fetchall()
        return [r["portfolio_group"] for r in rows]
    except sqlite3.Error as exc:
        raise DatabaseError(f"读取组合失败：{exc}") from exc
    finally:
        conn.close()


def move_group(db_path: str, old: str, new: str) -> int:
    """把 `old` 组合的全部交易改到 `new`，返回改动行数。

    改名与合并共用这一条 SQL——「把 A 并进 B」就是把 A 的名字改成 B。
    单条 UPDATE 自身就是一个事务，满足「改历史数据要么全成要么全不成」；
    出错回滚再抛，与 `add_many` 同一套语义。
    """
    conn = connect(db_path)
    try:
        cur = conn.execute(
            "UPDATE transactions SET portfolio_group = ? WHERE portfolio_group = ?",
            (new, old),
        )
        conn.commit()
        return cur.rowcount
    except sqlite3.Error as exc:
        conn.rollback()
        raise DatabaseError(f"改动组合失败：{exc}") from exc
    finally:
        conn.close()
