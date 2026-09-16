"""资产基础信息服务：标的名称、币种与年化管理费率的读写。

CLI 经由本模块访问 `asset_meta_dao`（架构铁律 3）。
"""

from __future__ import annotations

from holdings.models.asset_meta import AssetMeta
from holdings.storage import asset_meta_dao


def record(db_path: str, meta: AssetMeta) -> None:
    """写入或覆盖一条基础信息（`symbol` 是主键）。"""
    asset_meta_dao.upsert(db_path, meta)


def get(db_path: str, symbol: str) -> AssetMeta | None:
    """按代码取一条；没有记录时返回 `None`。"""
    return asset_meta_dao.get(db_path, symbol)


def remove(db_path: str, symbol: str) -> bool:
    """按代码删除，返回是否真的删掉了一条。"""
    return asset_meta_dao.delete(db_path, symbol)


def fee_rate_total(db_path: str, symbols: list[str]) -> float:
    """给定标的的年化管理费率合计（百分数）。

    只为报表展示——**不参与任何成本计算**。真实费用靠 `transactions.fee`
    逐笔记录，这里只是把「你填过的费率加起来是多少」如实报出来。
    """
    wanted = set(symbols)
    return sum(
        m.annual_management_fee for m in asset_meta_dao.get_all(db_path) if m.symbol in wanted
    )
