"""SQLite 连接管理与建表迁移。

仅负责数据库的创建与连接，不做任何业务计算。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from holdings.exceptions import DatabaseError

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_group TEXT DEFAULT '默认',
    symbol TEXT NOT NULL,
    market TEXT NOT NULL,
    asset_type TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    trade_type TEXT NOT NULL,
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    fee REAL DEFAULT 0,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date TEXT NOT NULL UNIQUE,
    total_value REAL NOT NULL,
    cash_balance REAL DEFAULT 0,
    equity_value REAL NOT NULL,
    gold_value REAL NOT NULL,
    note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS asset_meta (
    symbol TEXT PRIMARY KEY,
    name TEXT,
    market TEXT,
    currency TEXT DEFAULT 'CNY',
    annual_management_fee REAL DEFAULT 0,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS price_cache (
    symbol TEXT PRIMARY KEY,
    price REAL NOT NULL,
    currency TEXT DEFAULT 'CNY',
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source TEXT
);

CREATE INDEX IF NOT EXISTS idx_trans_symbol ON transactions(symbol);
CREATE INDEX IF NOT EXISTS idx_trans_date ON transactions(trade_date);
CREATE INDEX IF NOT EXISTS idx_cache_time ON price_cache(update_time);
"""


def connect(db_path: str) -> sqlite3.Connection:
    """建立连接并启用外键，自动建表。"""
    try:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DatabaseError(f"无法创建数据库目录：{exc}") from exc

    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        init_schema(conn)
    except Exception:
        # 建表失败时显式关闭，否则这条异常路径会把连接句柄泄漏掉。
        conn.close()
        raise
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """执行建表、补列迁移与索引创建。"""
    try:
        conn.executescript(SCHEMA_SQL)
        _migrate(conn)
        conn.commit()
    except sqlite3.Error as exc:
        raise DatabaseError(f"数据库建表失败：{exc}") from exc


def _migrate(conn: sqlite3.Connection) -> None:
    """给已存在的旧库补上后来新增的列。

    `CREATE TABLE IF NOT EXISTS` 对**已经存在**的表完全不会生效，所以历史上
    新增的列不会自己出现在老库里——必须显式探测再补。判定用 `PRAGMA table_info`
    而不是版本号：这个库由用户直接拿着用，不会有谁去维护一个 schema_version，
    而「这一列在不在」是自证的，也就不存在版本号与事实不符的问题。
    """
    if "note" not in _columns(conn, "snapshots"):
        conn.execute("ALTER TABLE snapshots ADD COLUMN note TEXT")


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """表当前实际有哪些列；表不存在时返回空集合。

    取 `row[1]`（PRAGMA table_info 的第 2 列是列名）而不是 `row["name"]`：
    拿到一个没设 row_factory 的连接时，行就是普通元组，用列名取会直接
    TypeError。这里只关心事实，不关心调用方怎么配连接。
    """
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
