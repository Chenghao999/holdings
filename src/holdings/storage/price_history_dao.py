"""历史收盘价的本地缓存（B-39）。

`price_cache` 对一个代码只存一行「最新价」，而基准对比要的是一段**序列**：
形状不同，所以另起一张表，而不是给 `price_cache` 加列。

主键 `(symbol, trade_date)`——一个代码一个交易日一个收盘价。同一段区间重复
取数时按主键**合并**写入，不是清空重写：已经有的日子不必再打一次网络，而用户
把 `--start` 往前挪时，新取回来的那一段会补进来。

这张表目前只装**指数**的历史（A 股走指数端点，见 `data/history.py`），
所以 `symbol` 单独做主键是够的。将来若把个股历史也存进来，`000001`
会同时是上证指数与平安银行，那时主键得带上市场或类型。
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from holdings.storage.db import DatabaseError, connect, timestamp_is_fresh

#: 判断「缓存盖住了这次要的区间」时，两端各放宽的天数。
#:
#: 区间边缘落在周末或长假上时，那几天**本来就不会有行**（非交易日没有收盘价），
#: 逐日精确比对会把它判成「没盖住」，于是每次跑都白打一遍网络。放宽 10 天盖得住
#: 最长的长假（春节 / 国庆连休 8 天），又不足以掩盖「用户把 `--start` 往前挪了
#: 三个月」那种**真的**没盖住的情形——那正是这一条要拦的静默少一段。
RANGE_SLACK_DAYS = 10


def get_range(db_path: str, symbol: str, start: date, end: date) -> list[tuple[date, float]]:
    """区间内的收盘价，按交易日升序。一行都没有就是空列表，不是错误。"""
    conn = connect(db_path)
    try:
        rows = conn.execute(
            "SELECT trade_date, close FROM price_history "
            "WHERE symbol = ? AND trade_date BETWEEN ? AND ? ORDER BY trade_date",
            (symbol, start.isoformat(), end.isoformat()),
        ).fetchall()
        return [(date.fromisoformat(row["trade_date"]), float(row["close"])) for row in rows]
    except sqlite3.Error as exc:
        raise DatabaseError(f"读取历史行情失败：{exc}") from exc
    finally:
        conn.close()


def upsert_many(db_path: str, symbol: str, rows: list[tuple[date, float]], source: str) -> int:
    """按 `(symbol, trade_date)` 合并写入，返回写入的行数。空列表直接返回 0。"""
    if not rows:
        return 0
    conn = connect(db_path)
    try:
        conn.executemany(
            "INSERT INTO price_history (symbol, trade_date, close, source) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(symbol, trade_date) DO UPDATE SET "
            "close = excluded.close, source = excluded.source, updated_at = CURRENT_TIMESTAMP",
            [(symbol, day.isoformat(), close, source) for day, close in rows],
        )
        conn.commit()
        return len(rows)
    except sqlite3.Error as exc:
        raise DatabaseError(f"写入历史行情失败：{exc}") from exc
    finally:
        conn.close()


def is_fresh(db_path: str, symbol: str, start: date, end: date, ttl_seconds: int) -> bool:
    """缓存是否**有、够新、且盖得住**这次要的区间。

    三条同时满足才算命中；缺一条就当成一次真实取数——重复取数是安全的
    （`upsert_many` 是合并写），只是多打一次网络：

    - **有**：这个代码一条历史都没有过。
    - **盖得住**：`MIN(trade_date)` 不晚于 `start + RANGE_SLACK_DAYS`，且
      `MAX(trade_date)` 不早于 `end - RANGE_SLACK_DAYS`。这一条防的是**静默
      少一段**：用户把 `--start` 往前挪，缓存里没有那一段，若只判「有没有行」，
      就会拿一段缺了开头的序列去算收益——算出来的数看着完全正常。
    - **够新**：最新一次的 `updated_at` 还在 TTL 内。TTL 判定走
      `db.timestamp_is_fresh`：SQLite 的 `CURRENT_TIMESTAMP` 存的是 UTC，
      拿本地时间比会整整差 8 小时（B-14 的教训），别再抄第二份。
    """
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT MIN(trade_date) AS first, MAX(trade_date) AS last, "
            "MAX(updated_at) AS updated FROM price_history WHERE symbol = ?",
            (symbol,),
        ).fetchone()
    except sqlite3.Error as exc:
        raise DatabaseError(f"读取历史行情失败：{exc}") from exc
    finally:
        conn.close()

    if row["first"] is None or not timestamp_is_fresh(row["updated"], ttl_seconds):
        return False
    slack = timedelta(days=RANGE_SLACK_DAYS)
    return (
        date.fromisoformat(row["first"]) <= start + slack
        and date.fromisoformat(row["last"]) >= end - slack
    )
