"""portfolio.calculator 加权平均成本算法的单元测试。"""

from datetime import date

from holdings.models.enums import AssetType, MarketType, TradeType
from holdings.models.transaction import Transaction
from holdings.portfolio.calculator import compute_positions, fee_breakdown, holding_for


def _tx(trade_type, qty, price, fee=0.0, symbol="600519"):
    return Transaction(
        symbol=symbol,
        market=MarketType.A_SHARE,
        asset_type=AssetType.STOCK,
        trade_date=date(2025, 1, 1),
        trade_type=TradeType(trade_type),
        quantity=qty,
        price=price,
        fee=fee,
    )


def test_buy_includes_fee_in_cost():
    txs = [_tx("BUY", 100, 10.0, fee=5.0)]
    positions = compute_positions(txs)
    pos = positions["600519"]
    # 新成本 = (0*0 + 100*10 + 5) / 100 = 10.05
    assert pos.quantity == 100
    assert round(pos.avg_cost, 4) == 10.05
    assert round(pos.total_fees, 4) == 5.0


def test_weighted_average_cost():
    txs = [
        _tx("BUY", 100, 10.0, fee=0.0),
        _tx("BUY", 100, 20.0, fee=0.0),
    ]
    pos = compute_positions(txs)["600519"]
    # (100*10 + 100*20) / 200 = 15
    assert pos.quantity == 200
    assert round(pos.avg_cost, 4) == 15.0


def test_sell_keeps_cost_price():
    txs = [
        _tx("BUY", 100, 10.0, fee=0.0),
        _tx("SELL", 40, 12.0, fee=0.0),
    ]
    pos = compute_positions(txs)["600519"]
    assert pos.quantity == 60
    # 成本价保持不变
    assert round(pos.avg_cost, 4) == 10.0
    # 已实现盈亏 = (12 - 10) * 40 = 80
    assert round(pos.realized_pnl, 4) == 80.0


def test_fee_does_not_change_position():
    txs = [
        _tx("BUY", 100, 10.0, fee=0.0),
        _tx("FEE", 0, 0.0, fee=12.5),
    ]
    pos = compute_positions(txs)["600519"]
    assert pos.quantity == 100
    assert round(pos.avg_cost, 4) == 10.0
    assert round(pos.total_fees, 4) == 12.5


def test_holding_profit_and_rate():
    txs = [_tx("BUY", 100, 10.0, fee=0.0)]
    pos = compute_positions(txs)["600519"]
    h = holding_for(pos, current_price=11.0)
    # 盈亏 = (11 - 10) * 100 = 100，收益率 10%
    assert round(h.profit, 4) == 100.0
    assert round(h.profit_rate, 4) == 10.0


def test_fee_breakdown_by_symbol():
    txs = [
        _tx("BUY", 100, 10.0, fee=5.0, symbol="A"),
        _tx("BUY", 100, 10.0, fee=3.0, symbol="B"),
        _tx("FEE", 0, 0.0, fee=2.0, symbol="A"),
    ]
    bd = fee_breakdown(txs)
    assert bd == {"A": 7.0, "B": 3.0}
