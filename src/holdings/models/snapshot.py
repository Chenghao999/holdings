"""资产快照数据模型（DTO）。"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class Snapshot(BaseModel):
    """某时间点的总资产快照，对应数据库 `snapshots` 表。"""

    snapshot_date: date
    total_value: float
    equity_value: float
    gold_value: float
    cash_balance: float = 0.0
    created_at: datetime | None = None
    id: int | None = None
