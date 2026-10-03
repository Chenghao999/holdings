"""portfolio.calculator 加权平均成本算法的单元测试。"""

from datetime import date

import pytest

from holdings.exceptions import TradeValidationError
from holdings.models.enums import AssetType, MarketType, TradeType
from holdings.models.transaction import Transaction
from holdings.portfolio.calculator import (
    _HANDLERS,
    compute_positions,
    fee_breakdown,
    holding_for,
)


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


def test_holding_without_a_price_has_no_numbers():
    """没有行情时市值/盈亏/盈亏率都是 None，不是 0。

    按 0 算出来的盈亏率是 −100%，看着像血亏；实际只是还没同步过。
    """
    pos = compute_positions([_tx("BUY", 100, 10.0)])["600519"]

    h = holding_for(pos, current_price=None)

    assert h.current_price is None
    assert h.market_value is None
    assert h.profit is None
    assert h.profit_rate is None
    # 数量、成本价、累计费用与行情无关，照常给出
    assert h.quantity == 100
    assert h.avg_cost == 10.0


def test_holding_with_zero_cost_has_no_rate():
    """零成本持仓的收益率无定义——给 0.00% 会看着像「不赚不亏」这个结论。"""
    pos = compute_positions([_tx("BUY", 100, 0.0)])["600519"]

    h = holding_for(pos, current_price=11.0)

    assert h.market_value == 1100.0
    assert h.profit_rate is None


# --- 公司行为：分红 / 送股 / 转增（B-38）---------------------------------------
#
# 两类都沿用同一条列约定：金额 = `quantity × price`，`price` 永远是单价。
# 分红是「持股数 × 每股派息」，送转是「新增股数 × 0」。


def test_every_trade_type_has_a_handler():
    """给 `TradeType` 加了成员、却忘了在 `_HANDLERS` 里补一行，这里就红。

    从前这里是三个没有 `else` 的 `if`：新类型会被**静默吞掉**，退出码 0、
    数字看着也对，用户没有任何线索。最可能踩的是日后做配股的时候。
    """
    assert set(_HANDLERS) == set(TradeType)


def test_a_dividend_thins_the_cost_and_leaves_the_shares_alone():
    """100 股 @10 成本 1000；每 10 股派 5 元（每股 0.5）→ 成本价 9.5。"""
    pos = compute_positions([_tx("BUY", 100, 10.0), _tx("DIVIDEND", 100, 0.5)])["600519"]

    assert pos.quantity == 100, "分红不改变股数"
    assert pos.total_cost == pytest.approx(950.0)
    assert pos.avg_cost == pytest.approx(9.5)


def test_the_dividend_lands_in_the_profit_and_not_in_the_fees():
    """分红摊薄成本，报表的总盈亏里就自然含分红——这是选这个口径的理由。

    换成「记进 `fee`」会得到相反的结果：`holding_for` 把 `total_fees`
    从盈亏里**再减一次**，分红进了那一列等于被倒扣出去，还会混进累计费用。
    """
    pos = compute_positions([_tx("BUY", 100, 10.0), _tx("DIVIDEND", 100, 0.5)])["600519"]

    h = holding_for(pos, current_price=11.0)

    # 没有分红时是 (11 - 10) × 100 = 100；分红 50 之后应当是 150
    assert h.profit == pytest.approx(150.0)
    assert h.total_fees == 0.0


@pytest.mark.parametrize(
    ("bonus", "expected_quantity", "expected_avg_cost"),
    [(50, 150, 1000 / 150), (100, 200, 5.0)],
)
def test_a_bonus_share_dilutes_the_cost_without_adding_any(
    bonus, expected_quantity, expected_avg_cost
):
    """总成本不变、股数增加，成本价随之被摊薄。送 50 股与十送十各一例。"""
    pos = compute_positions([_tx("BUY", 100, 10.0), _tx("BONUS_SHARE", bonus, 0.0)])["600519"]

    assert pos.quantity == pytest.approx(expected_quantity)
    assert pos.total_cost == pytest.approx(1000.0)
    assert pos.avg_cost == pytest.approx(expected_avg_cost)


@pytest.mark.parametrize(
    "steps",
    [
        [("BUY", 100, 10.0)],
        [("BUY", 100, 10.0), ("SELL", 40, 12.0)],
        [("BUY", 100, 10.0), ("DIVIDEND", 100, 0.5)],
        [("BUY", 100, 10.0), ("BONUS_SHARE", 50, 0.0)],
        [
            ("BUY", 100, 10.0),
            ("DIVIDEND", 100, 0.5),
            ("BONUS_SHARE", 50, 0.0),
            ("SELL", 30, 12.0),
        ],
    ],
)
def test_total_cost_always_equals_avg_cost_times_quantity(steps):
    """恒等式 `total_cost == avg_cost × quantity`——`_sell` 靠它按比例减成本，
    公司行为也必须维持它，否则卖出一笔之后成本价会跳。
    """
    pos = compute_positions([_tx(*step) for step in steps])["600519"]

    assert pos.total_cost == pytest.approx(pos.avg_cost * pos.quantity)


@pytest.mark.parametrize(
    ("trade_type", "qty", "price", "held", "message"),
    [
        ("DIVIDEND", 0, 0.5, 100, "持股数必须大于 0"),
        ("DIVIDEND", 100, 0, 100, "每股派息必须大于 0"),
        ("DIVIDEND", 100, 0.5, 0, "账本上没有持仓"),
        ("BONUS_SHARE", 0, 0.0, 100, "股数必须大于 0"),
        ("BONUS_SHARE", 100, 3.0, 100, "单价必须为 0"),
        ("BONUS_SHARE", 100, 0.0, 0, "账本上没有持仓"),
    ],
)
def test_corporate_actions_are_checked_against_the_position_so_far(
    trade_type, qty, price, held, message
):
    """`held` 是「账本上此刻有多少股」：摊薄与加股都作用在既有持仓上。

    清仓之后才到账的分红确实存在，但那时无处可施——`realized_pnl` 目前没有
    任何界面展示，记进去等于凭空消失。宁可报错，让用户把日期记在持仓期间。
    """
    history = [_tx("BUY", held, 10.0)] if held else []

    with pytest.raises(TradeValidationError, match=message):
        compute_positions([*history, _tx(trade_type, qty, price)], strict=True)


@pytest.mark.parametrize("trade_type", ["BUY", "SELL"])
def test_a_negative_price_is_refused_for_both_directions(trade_type):
    """买卖的单价都不能为负。校验链改成按枚举分派之后，两条分支要各有一条用例。"""
    with pytest.raises(TradeValidationError, match="单价不能为负"):
        compute_positions([_tx("BUY", 100, 10.0), _tx(trade_type, 10, -1.0)], strict=True)


def test_holding_rate_is_undefined_when_the_cost_has_gone_negative():
    """分红摊薄到成本价为负会真实发生（长期持有，券商 APP 也这么显示）。

    `(现价 / 负成本 − 1) × 100` 是个 −1000% 量级的数：看着像结论，其实是
    符号翻了。**成本价照实显示负数**——那笔账是真的，只是收益率不给。
    """
    pos = compute_positions([_tx("BUY", 100, 1.0), _tx("DIVIDEND", 100, 3.0)])["600519"]

    h = holding_for(pos, current_price=2.0)

    assert h.avg_cost == pytest.approx(-2.0)
    assert h.profit == pytest.approx(400.0)
    assert h.profit_rate is None


def test_fee_breakdown_by_symbol():
    txs = [
        _tx("BUY", 100, 10.0, fee=5.0, symbol="A"),
        _tx("BUY", 100, 10.0, fee=3.0, symbol="B"),
        _tx("FEE", 0, 0.0, fee=2.0, symbol="A"),
    ]
    bd = fee_breakdown(txs)
    assert bd == {"A": 7.0, "B": 3.0}
