"""持仓成本与盈亏计算（纯函数）。

采用移动加权平均法：
- 买入：费用计入成本，`新成本 = (旧数量×旧成本 + 新数量×新价 + 新费用) / (旧数量 + 新数量)`。
- 卖出：数量减少，成本价保持不变。
- FEE：不改变数量与成本，仅累计费用。

本模块不依赖 storage / data，只接收交易序列做计算。
"""

from __future__ import annotations

from dataclasses import dataclass

from holdings.exceptions import TradeValidationError
from holdings.models.transaction import Transaction


@dataclass
class Position:
    """单标的持仓计算结果。"""

    symbol: str
    quantity: float = 0.0
    avg_cost: float = 0.0
    total_cost: float = 0.0  # 含费用的总成本
    total_fees: float = 0.0  # 累计费用
    realized_pnl: float = 0.0  # 已实现盈亏（卖出部分）


@dataclass
class Holding:
    """某标的某时间的最终持仓状态，可直接用于渲染与报表。

    `current_price` 为 `None` 表示**这只标的没有行情**（还没同步过，或者数据源
    没取到）。此时市值、盈亏、盈亏率**一律是 `None`，不是 0**：按 0 算出来的
    盈亏率是 −100%，用户看到的是「血亏 100%」，而事实只是「不知道」。
    渲染层据此显示 `—`。
    """

    symbol: str
    quantity: float
    avg_cost: float
    total_fees: float
    current_price: float | None = None
    market_value: float | None = None
    profit: float | None = None
    profit_rate: float | None = None


def _weighted_buy(pos: Position, tx: Transaction) -> None:
    new_qty = pos.quantity + tx.quantity
    total = pos.quantity * pos.avg_cost + tx.quantity * tx.price + tx.fee
    pos.quantity = new_qty
    pos.avg_cost = total / new_qty if new_qty else 0.0
    pos.total_cost += tx.quantity * tx.price + tx.fee
    pos.total_fees += tx.fee


def _sell(pos: Position, tx: Transaction) -> None:
    # 卖出成本价不变，已实现盈亏 = (卖出价 - 成本价) × 数量 - 费用
    pos.realized_pnl += (tx.price - pos.avg_cost) * tx.quantity - tx.fee
    pos.total_fees += tx.fee
    pos.quantity -= tx.quantity
    # 按比例减少总成本，保持成本价一致
    pos.total_cost = pos.avg_cost * pos.quantity
    if pos.quantity == 0:
        pos.avg_cost = 0.0


def _apply_fee(pos: Position, tx: Transaction) -> None:
    # FEE 不改变数量与成本，仅累计费用
    pos.total_fees += tx.fee


def check_trade(pos: Position | None, tx: Transaction) -> None:
    """校验单笔交易在**当前持仓状态**下是否合法，非法则抛 TradeValidationError。

    独立于重放逻辑导出，便于写入路径在落库前单独调用。
    """
    held = pos.quantity if pos else 0.0
    if tx.trade_type.value in ("BUY", "SELL") and tx.quantity <= 0:
        raise TradeValidationError(
            f"{tx.symbol} 的{tx.trade_type.value}数量必须大于 0，当前为 {tx.quantity}"
        )
    if tx.trade_type.value == "BUY" and tx.price < 0:
        raise TradeValidationError(f"{tx.symbol} 的买入单价不能为负，当前为 {tx.price}")
    if tx.trade_type.value == "SELL":
        if tx.price < 0:
            raise TradeValidationError(f"{tx.symbol} 的卖出单价不能为负，当前为 {tx.price}")
        # 这条校验此前缺失：卖出超过持有量会把数量算成负数，
        # 进而让总成本变成负数并被汇总悄悄吞掉（持仓在汇总时按数量<=0 跳过）。
        if tx.quantity > held:
            raise TradeValidationError(f"{tx.symbol} 卖出数量 {tx.quantity} 超过当时持有量 {held}")
    if tx.fee < 0:
        raise TradeValidationError(f"{tx.symbol} 的费用不能为负，当前为 {tx.fee}")


def compute_positions(
    transactions: list[Transaction], *, strict: bool = False
) -> dict[str, Position]:
    """按标的对已排序交易序列做加权平均计算。

    若传入的 transactions 无序，需先自行排序（按 trade_date, id）。

    `strict=True` 时在重放过程中逐笔校验，遇到非法交易立即抛 TradeValidationError。
    写入账本前应当开启；**读取历史账本时必须关闭**——旧数据里可能已经存在越界记录，
    开启会导致整段历史读不出来。汇总服务靠 `quantity <= 0` 跳过这类脏数据。
    """
    positions: dict[str, Position] = {}
    for tx in transactions:
        pos = positions.setdefault(tx.symbol, Position(symbol=tx.symbol))
        if strict:
            check_trade(pos, tx)
        if tx.trade_type.value == "BUY":
            _weighted_buy(pos, tx)
        elif tx.trade_type.value == "SELL":
            _sell(pos, tx)
        elif tx.trade_type.value == "FEE":
            _apply_fee(pos, tx)
    return positions


def holding_for(position: Position, current_price: float | None) -> Holding:
    """根据持仓与当前价计算盈亏与收益率。

    `current_price=None` 表示没有行情：市值、盈亏、盈亏率都是 `None`。
    零成本持仓（`avg_cost == 0`）的收益率同样无定义，一并给 `None`——
    比起一个看着像结论的 `0.00%`，「算不出来」才是实话。
    """
    if current_price is None:
        return Holding(
            symbol=position.symbol,
            quantity=position.quantity,
            avg_cost=position.avg_cost,
            total_fees=position.total_fees,
        )
    market_value = position.quantity * current_price
    profit = (current_price - position.avg_cost) * position.quantity - position.total_fees
    rate = (current_price / position.avg_cost - 1) * 100 if position.avg_cost else None
    return Holding(
        symbol=position.symbol,
        quantity=position.quantity,
        avg_cost=position.avg_cost,
        total_fees=position.total_fees,
        current_price=current_price,
        market_value=market_value,
        profit=profit,
        profit_rate=rate,
    )


def summarize(positions: dict[str, Position]) -> dict[str, float]:
    """汇总所有持仓的总额、总成本、总费用与已实现盈亏。"""
    total_quantity_based_cost = sum(p.quantity * p.avg_cost for p in positions.values())
    return {
        "total_cost": sum(p.total_cost for p in positions.values()),
        "total_fees": sum(p.total_fees for p in positions.values()),
        "realized_pnl": sum(p.realized_pnl for p in positions.values()),
        "net_cost": total_quantity_based_cost,
    }


@dataclass
class FeeItem:
    """单笔费用的分项。"""

    symbol: str
    amount: float


def fee_breakdown(transactions: list[Transaction]) -> dict[str, float]:
    """按标的分项汇总累计费用（BUY/SELL/FEE 的费用均计入）。"""
    result: dict[str, float] = {}
    for tx in transactions:
        if tx.fee:
            result[tx.symbol] = result.get(tx.symbol, 0.0) + tx.fee
    return result
