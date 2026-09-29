"""pytest 共享夹具。

所有涉及数据库的测试都走 `db_path`，指向临时文件，互不干扰。
"""

from datetime import date

import pytest

from holdings.data import instrument
from holdings.models.enums import AssetType, MarketType, TradeType
from holdings.models.transaction import Transaction


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """用例一律不触网：把标的资料的源表清空。

    `holdings import` 会按代码去数据源补名称与市场（BACKLOG B-32），而本机与
    CI 都可能装着 yfinance——不挡住的话，一次 `pytest` 会发出成百上千个真实
    请求：跑得慢、结果还随网络变，而失败长得像代码坏了。

    需要那条链路的用例自己往 `instrument._SOURCES` 里装假源，见
    `tests/test_instrument.py` 的 `fake_sources`。
    """
    monkeypatch.setattr(instrument, "_SOURCES", {})


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
        source: str | None = None,
        external_id: str | None = None,
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
            source=source,
            external_id=external_id,
        )

    return _make
