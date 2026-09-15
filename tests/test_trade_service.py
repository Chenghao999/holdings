"""交易写入服务测试：校验闸门与批量写入的原子性。"""

from __future__ import annotations

from datetime import date

import pytest

from holdings.exceptions import TradeValidationError
from holdings.services import trade_service
from holdings.storage import transaction_dao


def test_add_transaction_persists_valid_trade(db_path, make_tx):
    tx_id = trade_service.add_transaction(db_path, make_tx(qty=10, price=100))
    assert tx_id > 0
    assert len(transaction_dao.get_all(db_path)) == 1


def test_add_transaction_rejects_oversell(db_path, make_tx):
    trade_service.add_transaction(db_path, make_tx(trade_type="BUY", qty=10, price=100))
    with pytest.raises(TradeValidationError, match="超过当时持有量"):
        trade_service.add_transaction(
            db_path, make_tx(trade_type="SELL", qty=15, price=100, trade_date=date(2025, 1, 2))
        )
    # 被拒的交易不能落库
    assert len(transaction_dao.get_all(db_path)) == 1


def test_batch_is_all_or_nothing(db_path, make_tx):
    """CSV 导入依赖这个语义：任一笔非法则整批不写。"""
    batch = [
        make_tx(symbol="NVDA", qty=10, price=100),
        make_tx(symbol="TSLA", trade_type="SELL", qty=5, price=200),  # 从未持有，非法
    ]
    with pytest.raises(TradeValidationError):
        trade_service.add_transactions(db_path, batch)
    assert transaction_dao.get_all(db_path) == []


def test_batch_writes_all_when_valid(db_path, make_tx):
    ids = trade_service.add_transactions(
        db_path,
        [
            make_tx(symbol="NVDA", qty=10, price=100),
            make_tx(symbol="TSLA", qty=5, price=200, trade_date=date(2025, 1, 2)),
        ],
    )
    assert len(ids) == 2
    assert len(transaction_dao.get_all(db_path)) == 2


def test_empty_batch_is_noop(db_path):
    assert trade_service.add_transactions(db_path, []) == []
    assert transaction_dao.get_all(db_path) == []


def test_backdated_sell_is_validated_against_position_at_that_time(db_path, make_tx):
    """补录往日交易时，须按当时的持仓状态判断，而不是按今天的持仓。"""
    trade_service.add_transaction(
        db_path, make_tx(trade_type="BUY", qty=10, price=100, trade_date=date(2025, 1, 1))
    )
    trade_service.add_transaction(
        db_path, make_tx(trade_type="BUY", qty=10, price=100, trade_date=date(2025, 3, 1))
    )
    # 2025-02-01 时只持有 10 股，卖 15 股应当被拒
    with pytest.raises(TradeValidationError, match="超过当时持有量"):
        trade_service.add_transaction(
            db_path, make_tx(trade_type="SELL", qty=15, price=100, trade_date=date(2025, 2, 1))
        )


def test_backdated_sell_within_held_amount_is_accepted(db_path, make_tx):
    trade_service.add_transaction(
        db_path, make_tx(trade_type="BUY", qty=10, price=100, trade_date=date(2025, 1, 1))
    )
    trade_service.add_transaction(
        db_path, make_tx(trade_type="BUY", qty=10, price=100, trade_date=date(2025, 3, 1))
    )
    trade_service.add_transaction(
        db_path, make_tx(trade_type="SELL", qty=8, price=120, trade_date=date(2025, 2, 1))
    )
    txs = transaction_dao.get_all(db_path)
    assert [t.trade_date for t in txs] == [
        date(2025, 1, 1),
        date(2025, 2, 1),
        date(2025, 3, 1),
    ]
