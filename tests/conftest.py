"""pytest 共享夹具。

所有涉及数据库的测试都走 `db_path`，指向临时文件，互不干扰。
"""

from datetime import date

import pytest

from holdings.models.enums import AssetType, MarketType, TradeType
from holdings.models.transaction import Transaction


@pytest.fixture
def db_path(tmp_path) -> str:
    """指向临时文件的数据库路径（首次 connect 时自动建表）。"""
    return str(tmp_path / "holdings.db")


@pytest.fixture
def make_tx():
    """构造 Transaction 的工厂，默认值即一笔最普通的 A 股买入。"""

    def _make(
        symbol: str = "600519",
        market: MarketType = MarketType.A_SHARE,
        asset_type: AssetType = AssetType.STOCK,
        trade_date: date = date(2025, 1, 1),
        trade_type: str = "BUY",
        qty: float = 100.0,
        price: float = 10.0,
        fee: float = 0.0,
        group: str = "默认",
        notes: str | None = None,
    ) -> Transaction:
        return Transaction(
            symbol=symbol,
            market=market,
            asset_type=asset_type,
            trade_date=trade_date,
            trade_type=TradeType(trade_type),
            quantity=qty,
            price=price,
            fee=fee,
            portfolio_group=group,
            notes=notes,
        )

    return _make
