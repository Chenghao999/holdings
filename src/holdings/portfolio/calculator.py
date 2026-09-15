"""持仓成本与盈亏计算（纯函数）。

采用移动加权平均法：
- 买入：费用计入成本，`新成本 = (旧数量×旧成本 + 新数量×新价 + 新费用) / (旧数量 + 新数量)`。
- 卖出：数量减少，成本价保持不变。
- FEE：不改变数量与成本，仅累计费用。

本模块不依赖 storage / data，只接收交易序列做计算。
"""

from __future__ import annotations

from dataclasses import dataclass

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
    """某标的某时间的最终持仓状态，可直接用于渲染与报表。"""

    symbol: str
    quantity: float
    avg_cost: float
    total_fees: float
    current_price: float = 0.0
    market_value: float = 0.0
    profit: float = 0.0
    profit_rate: float = 0.0


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


def compute_positions(transactions: list[Transaction]) -> dict[str, Position]:
    """按标的对已排序交易序列做加权平均计算。

    若传入的 transactions 无序，需先自行排序（按 trade_date, id）。
    """
    positions: dict[str, Position] = {}
    for tx in transactions:
        pos = positions.setdefault(tx.symbol, Position(symbol=tx.symbol))
        if tx.trade_type.value == "BUY":
            _weighted_buy(pos, tx)
        elif tx.trade_type.value == "SELL":
            _sell(pos, tx)
        elif tx.trade_type.value == "FEE":
            _apply_fee(pos, tx)
    return positions


def holding_for(position: Position, current_price: float) -> Holding:
    """根据持仓与当前价计算盈亏与收益率。"""
    market_value = position.quantity * current_price
    profit = (current_price - position.avg_cost) * position.quantity - position.total_fees
    rate = (current_price / position.avg_cost - 1) * 100 if position.avg_cost else 0.0
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
