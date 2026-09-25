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


# --- 查重（B-29）--------------------------------------------------------------
#
# `find_duplicates` 只**报告**，丢不丢由 `import --dedupe` 决定。
# 下面的用例锁的是「什么算同一笔」——它错一次，用户的账就多一次或少一次。


def test_a_row_already_in_the_ledger_is_found(db_path, make_tx):
    tx_id = trade_service.add_transaction(db_path, make_tx(qty=10, price=100))

    duplicates = trade_service.find_duplicates(db_path, [make_tx(qty=10, price=100)])

    assert [(d.index, d.existing_id) for d in duplicates] == [(0, tx_id)]


def test_a_repeat_inside_one_batch_is_found(db_path, make_tx):
    """同一批里前面出现过一模一样的，也算重复。

    有些券商自己的导出就带重复行；只查库的话，这种文件仍会静默把账翻倍，
    而它和「逐月导出有重叠」是同一件事。
    """
    batch = [make_tx(qty=10, price=100), make_tx(qty=10, price=100)]

    duplicates = trade_service.find_duplicates(db_path, batch)

    assert [(d.index, d.existing_id, d.earlier) for d in duplicates] == [(1, None, 0)]


def test_nothing_is_reported_when_every_row_is_new(db_path, make_tx):
    assert trade_service.find_duplicates(db_path, [make_tx(qty=10, price=100)]) == []


@pytest.mark.parametrize(
    ("field", "kwargs"),
    [
        ("标的", {"symbol": "NVDA"}),
        ("日期", {"trade_date": date(2025, 1, 2)}),
        ("方向", {"trade_type": "SELL"}),
        ("数量", {"qty": 11}),
        ("价格", {"price": 101}),
        ("费用", {"fee": 5.0}),
    ],
)
def test_the_fingerprint_covers_every_field_it_claims_to(db_path, make_tx, field, kwargs):
    """指纹说好了是「标的 + 日期 + 类型 + 数量 + 价格 + 费用」，六个都要算进去。

    漏掉任何一个，被漏的那个字段改了也会判成同一笔——用户按这份报告加
    `--dedupe skip`，那一笔就真被丢掉了。
    """
    trade_service.add_transaction(db_path, make_tx(qty=10, price=100))

    assert trade_service.find_duplicates(db_path, [make_tx(**kwargs)]) == [], field


def test_the_portfolio_group_is_not_part_of_the_fingerprint(db_path, make_tx):
    """同一笔交易记进另一个组合，仍是重复——两个组合都会被汇总进总市值。

    这是有意为之：把组合放进指纹，「同一份对账单导进两个组合」就会被放行，
    而那正是本项要防的双计。
    """
    trade_service.add_transaction(db_path, make_tx(qty=10, price=100))

    duplicates = trade_service.find_duplicates(
        db_path, [make_tx(qty=10, price=100, group="养老金")]
    )

    assert len(duplicates) == 1


def test_an_external_id_beats_the_fingerprint(db_path, make_tx):
    """有流水号时按流水号判重，指纹退居其次。

    这是指纹唯一的出路：同一天同价同费分两笔买 100 股是真实存在的成交，
    指纹分不开它们，券商的流水号能。
    """
    trade_service.add_transaction(
        db_path, make_tx(qty=10, price=100, source="csv", external_id="HT-1")
    )

    # 其余字段完全一样，只有流水号不同 → 是两笔
    assert (
        trade_service.find_duplicates(
            db_path, [make_tx(qty=10, price=100, source="csv", external_id="HT-2")]
        )
        == []
    )
    # 流水号一样 → 是同一笔
    assert (
        len(
            trade_service.find_duplicates(
                db_path, [make_tx(qty=10, price=100, source="csv", external_id="HT-1")]
            )
        )
        == 1
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
