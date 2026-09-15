"""交易合法性校验测试。

覆盖此前缺失的领域校验：卖出超过持有量会让数量与总成本双双转负，
并被汇总按「数量 <= 0」悄悄跳过，属于静默的数据损坏。
"""

from __future__ import annotations

from datetime import date

import pytest

from holdings.exceptions import TradeValidationError
from holdings.portfolio import calculator


def test_sell_more_than_held_is_rejected(make_tx):
    txs = [
        make_tx(trade_type="BUY", qty=10, price=100),
        make_tx(trade_type="SELL", qty=15, price=100, trade_date=date(2025, 1, 2)),
    ]
    with pytest.raises(TradeValidationError, match="超过当时持有量"):
        calculator.compute_positions(txs, strict=True)


def test_sell_exactly_held_is_allowed(make_tx):
    txs = [
        make_tx(trade_type="BUY", qty=10, price=100),
        make_tx(trade_type="SELL", qty=10, price=120, trade_date=date(2025, 1, 2)),
    ]
    positions = calculator.compute_positions(txs, strict=True)
    assert positions["600519"].quantity == 0


def test_sell_without_any_holding_is_rejected(make_tx):
    with pytest.raises(TradeValidationError, match="超过当时持有量"):
        calculator.compute_positions([make_tx(trade_type="SELL", qty=1, price=10)], strict=True)


@pytest.mark.parametrize("qty", [0.0, -5.0])
def test_non_positive_buy_quantity_is_rejected(make_tx, qty):
    with pytest.raises(TradeValidationError, match="必须大于 0"):
        calculator.compute_positions([make_tx(trade_type="BUY", qty=qty)], strict=True)


def test_negative_fee_is_rejected(make_tx):
    with pytest.raises(TradeValidationError, match="费用不能为负"):
        calculator.compute_positions([make_tx(fee=-1.0)], strict=True)


def test_negative_price_is_rejected(make_tx):
    with pytest.raises(TradeValidationError, match="单价不能为负"):
        calculator.compute_positions([make_tx(price=-1.0)], strict=True)


def test_fee_transaction_may_carry_zero_quantity_and_price(make_tx):
    """FEE 只累计费用，数量与单价本就为 0，不应被数量校验拦下。"""
    txs = [make_tx(trade_type="FEE", qty=0.0, price=0.0, fee=12.5)]
    positions = calculator.compute_positions(txs, strict=True)
    assert positions["600519"].total_fees == 12.5


def test_strict_off_still_reads_dirty_history(make_tx):
    """读取历史账本必须容忍越界记录，否则旧数据整段读不出来。"""
    txs = [
        make_tx(trade_type="BUY", qty=10, price=100),
        make_tx(trade_type="SELL", qty=15, price=100, trade_date=date(2025, 1, 2)),
    ]
    positions = calculator.compute_positions(txs)  # strict 默认为 False
    assert positions["600519"].quantity == -5


def test_check_trade_reports_symbol_in_message(make_tx):
    positions = calculator.compute_positions([make_tx(symbol="NVDA", qty=1)])
    with pytest.raises(TradeValidationError, match="NVDA"):
        calculator.check_trade(positions["NVDA"], make_tx(symbol="NVDA", trade_type="SELL", qty=2))


def test_check_trade_accepts_none_position_for_first_buy(make_tx):
    calculator.check_trade(None, make_tx(trade_type="BUY", qty=1))
