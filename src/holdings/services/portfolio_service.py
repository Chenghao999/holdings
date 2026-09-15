"""持仓汇总服务：编排 storage + portfolio，返回纯数据对象。"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from holdings.models.enums import MarketType
from holdings.portfolio import allocator, calculator
from holdings.storage import transaction_dao


@dataclass
class PortfolioSummary:
    """持仓汇总结果，纯数据，供 CLI / GUI 渲染。"""

    total_value: float
    total_cost: float
    total_profit: float
    profit_rate: float
    total_fees: float
    allocation: dict
    holdings_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    fee_breakdown: dict = field(default_factory=dict)


def get_summary(db_path: str, group: str | None = None) -> PortfolioSummary:
    """计算持仓汇总，不输出任何文字。"""
    transactions = transaction_dao.get_all(db_path, group=group)
    positions = calculator.compute_positions(transactions)

    # 资产类型映射（用于配置占比）
    asset_types = {t.symbol: t.asset_type.value for t in transactions}

    # 含费用汇总
    sums = calculator.summarize(positions)
    total_cost = sums["total_cost"]
    total_fees = sums["total_fees"]

    # 每个标的的当前价（剩余持仓量 > 0 的略过无意义条目）
    from holdings.storage import price_cache_dao

    holdings_rows = []
    total_value = 0.0
    for symbol, pos in positions.items():
        if pos.quantity <= 0:
            continue
        cached = price_cache_dao.get(db_path, symbol)
        current_price = cached.price if cached else 0.0
        h = calculator.holding_for(pos, current_price)
        holdings_rows.append(
            {
                "symbol": h.symbol,
                "market": _market_of(transactions, symbol),
                "asset_type": asset_types.get(symbol, "stock"),
                "quantity": h.quantity,
                "avg_cost": round(h.avg_cost, 4),
                "current_price": h.current_price,
                "market_value": h.market_value,
                "total_fees": round(h.total_fees, 4),
                "profit": h.profit,
                "profit_rate": h.profit_rate,
            }
        )
        total_value += h.market_value

    holdings_df = pd.DataFrame(holdings_rows)
    total_profit = holdings_df["profit"].sum() if not holdings_df.empty else 0.0
    profit_rate = (total_profit / total_cost * 100) if total_cost else 0.0

    market_values = {r["symbol"]: r["market_value"] for r in holdings_rows}
    alloc = allocator.allocation_by_asset_type(market_values, asset_types)

    return PortfolioSummary(
        total_value=total_value,
        total_cost=total_cost,
        total_profit=total_profit,
        profit_rate=profit_rate,
        total_fees=total_fees,
        allocation=alloc,
        holdings_df=holdings_df,
        fee_breakdown=calculator.fee_breakdown(transactions),
    )


def _market_of(transactions, symbol: str) -> str:
    for t in transactions:
        if t.symbol == symbol:
            return t.market.value
    return MarketType.A_SHARE.value
