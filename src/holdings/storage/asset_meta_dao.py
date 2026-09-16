"""资产基础信息（`asset_meta` 表）的 CRUD。

与其余三个 DAO 同构：签名收 `db_path`、内部 `connect()` + `try/finally`、
异常统一包成 `DatabaseError`。

这张表此前只有建表语句、全项目零引用：`SCHEMA.md` 定义并详解了它（含
`annual_management_fee`），正文写着「完整支持基金托管费」，但没有任何代码读写。
"""

from __future__ import annotations

import sqlite3
from datetime import datetime

from holdings.models.asset_meta import AssetMeta
from holdings.storage.db import DatabaseError, connect

_UPSERT_SQL = """
INSERT INTO asset_meta (symbol, name, market, currency, annual_management_fee, updated_at)
VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
ON CONFLICT(symbol) DO UPDATE SET
    name = excluded.name,
    market = excluded.market,
    currency = excluded.currency,
    annual_management_fee = excluded.annual_management_fee,
    updated_at = CURRENT_TIMESTAMP
"""


def _row_to_asset_meta(row: sqlite3.Row) -> AssetMeta:
    return AssetMeta(
        symbol=row["symbol"],
        name=row["name"],
        market=row["market"],
        currency=row["currency"],
        annual_management_fee=row["annual_management_fee"],
        updated_at=(datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None),
    )


def get(db_path: str, symbol: str) -> AssetMeta | None:
    """按代码取一条；没有记录时返回 None（不是造一条默认值出来）。"""
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT * FROM asset_meta WHERE symbol = ?", (symbol,)).fetchone()
        return _row_to_asset_meta(row) if row else None
    except sqlite3.Error as exc:
        raise DatabaseError(f"读取资产信息失败：{exc}") from exc
    finally:
        conn.close()


def get_all(db_path: str) -> list[AssetMeta]:
    """取全部。`list` 要给每个持仓配名称、`report` 要算费率合计，
    逐条 `get` 会变成 N+1 次查询。"""
    conn = connect(db_path)
    try:
        rows = conn.execute("SELECT * FROM asset_meta ORDER BY symbol").fetchall()
        return [_row_to_asset_meta(r) for r in rows]
    except sqlite3.Error as exc:
        raise DatabaseError(f"读取资产信息失败：{exc}") from exc
    finally:
        conn.close()


def upsert(db_path: str, meta: AssetMeta) -> None:
    """按代码写入或覆盖。

    用 `ON CONFLICT DO UPDATE` 而不是先查后写：`symbol` 是主键，一条语句就能
    表达「有则更新、无则插入」，也省掉了两次查询之间的竞态。
    """
    conn = connect(db_path)
    try:
        conn.execute(
            _UPSERT_SQL,
            (
                meta.symbol,
                meta.name,
                meta.market,
                meta.currency,
                meta.annual_management_fee,
            ),
        )
        conn.commit()
    except sqlite3.Error as exc:
        raise DatabaseError(f"写入资产信息失败：{exc}") from exc
    finally:
        conn.close()


def delete(db_path: str, symbol: str) -> bool:
    """按代码删除，返回是否真的删掉了一条。"""
    conn = connect(db_path)
    try:
        cur = conn.execute("DELETE FROM asset_meta WHERE symbol = ?", (symbol,))
        conn.commit()
        return cur.rowcount > 0
    except sqlite3.Error as exc:
        raise DatabaseError(f"删除资产信息失败：{exc}") from exc
    finally:
        conn.close()
