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
    #: 备注。不传就是 None（数据库里存 NULL），而不是空串——
    #: 「没写备注」与「写了个空备注」在查询与展示上应当是两回事。
    note: str | None = None
    created_at: datetime | None = None
    id: int | None = None
