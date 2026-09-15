"""资产快照的 CRUD。"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime

from holdings.models.snapshot import Snapshot
from holdings.storage.db import DatabaseError, connect


def _row_to_snapshot(row: sqlite3.Row) -> Snapshot:
    return Snapshot(
        id=row["id"],
        snapshot_date=date.fromisoformat(row["snapshot_date"]),
        total_value=row["total_value"],
        cash_balance=row["cash_balance"],
        equity_value=row["equity_value"],
        gold_value=row["gold_value"],
        note=row["note"],
        created_at=(datetime.fromisoformat(row["created_at"]) if row["created_at"] else None),
    )


def add(db_path: str, snap: Snapshot) -> int:
    conn = connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO snapshots (snapshot_date, total_value, cash_balance, "
            "equity_value, gold_value, note) VALUES (?, ?, ?, ?, ?, ?)",
            (
                snap.snapshot_date.isoformat(),
                snap.total_value,
                snap.cash_balance,
                snap.equity_value,
                snap.gold_value,
                snap.note,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)
    except sqlite3.IntegrityError as exc:
        raise DatabaseError(f"该日期快照已存在：{snap.snapshot_date}") from exc
    except sqlite3.Error as exc:
        raise DatabaseError(f"新增快照失败：{exc}") from exc
    finally:
        conn.close()


def get_all(db_path: str) -> list[Snapshot]:
    conn = connect(db_path)
    try:
        rows = conn.execute("SELECT * FROM snapshots ORDER BY snapshot_date").fetchall()
        return [_row_to_snapshot(r) for r in rows]
    except sqlite3.Error as exc:
        raise DatabaseError(f"读取快照失败：{exc}") from exc
    finally:
        conn.close()
