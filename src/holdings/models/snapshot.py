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
    #: **上一次快照之后、到这一天为止**的净入金：入金为正、出金为负，默认 0。
    #:
    #: 默认值 `0` 是一句**断言**「这段时间没有出入金」，不是「未记录」——基准对比
    #: （B-39）拿它把入金从收益里剔除，真没记而实际有出入金，那笔钱会被算成收益。
    #: 之所以不用 `None` 表示「未申报」：手记快照本来就是稀疏的，绝大多数区间
    #: 确实没有出入金，让每一条都挂个「未申报」只是噪音；口径句里点出这条约定，
    #: 比一个填不过来的字段诚实。
    external_flow: float = 0.0
    #: 备注。不传就是 None（数据库里存 NULL），而不是空串——
    #: 「没写备注」与「写了个空备注」在查询与展示上应当是两回事。
    note: str | None = None
    created_at: datetime | None = None
    id: int | None = None
