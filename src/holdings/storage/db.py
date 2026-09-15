"""SQLite 连接管理与建表迁移。

仅负责数据库的创建与连接，不做任何业务计算。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

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


class DatabaseError(Exception):
    """数据库读写失败。"""


def connect(db_path: str) -> sqlite3.Connection:
    """建立连接并启用外键，自动建表。"""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_schema(conn)
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """执行建表与索引迁移。"""
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    except sqlite3.Error as exc:
        raise DatabaseError(f"数据库建表失败：{exc}") from exc
