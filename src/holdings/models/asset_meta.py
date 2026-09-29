"""资产基础信息数据模型（DTO）。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from holdings.models.enums import AssetType


class AssetMeta(BaseModel):
    """某标的的基础信息，对应数据库 `asset_meta` 表。

    ⚠️ **`annual_management_fee` 只作参考展示，不参与任何成本计算。**

    它是年化管理费率（如基金托管费），单位是**百分数**（`0.5` 表示 0.5%）。
    真实费用由 `transactions.fee` 逐笔记录。不要在这里做「按持仓天数自动计提」——
    那会让 `list` 的成本价随日历漂移，与移动加权平均成本法直接冲突，
    也与 [SCHEMA.md](../../../docs/SCHEMA.md) 对该字段的定义矛盾。
    """

    symbol: str
    name: str | None = None
    market: str | None = None
    #: 资产类型。**允许为空**：不是每个数据源都分得出股票与 ETF，而猜一个
    #: 错的类型会一路走进报表，用户却看不出那是猜的。
    asset_type: AssetType | None = None
    currency: str = "CNY"
    annual_management_fee: float = 0.0
    updated_at: datetime | None = None
