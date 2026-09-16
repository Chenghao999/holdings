"""持仓汇总服务：编排 storage + portfolio，返回纯数据对象。"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from holdings.models.enums import MarketType
from holdings.portfolio import allocator, calculator
from holdings.storage import asset_meta_dao, price_cache_dao, transaction_dao


@dataclass
class PortfolioSummary:
    """持仓汇总结果，纯数据，供 CLI / GUI 渲染。

    **汇总的口径是「有行情的标的」。** 没有行情的标的市值算不出来，让它以 0
    参与汇总，就是 `list` 里那个「血亏 100%」的来源。没被计入的部分用
    `unpriced_symbols` / `unpriced_cost` 如实报出来，由渲染层提示用户去 sync。
    """

    total_value: float
    total_cost: float
    total_profit: float | None
    profit_rate: float | None
    total_fees: float
    allocation: dict
    holdings_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    fee_breakdown: dict = field(default_factory=dict)
    #: 没有行情的标的（按代码）。非空时汇总行里的市值与盈亏都只覆盖其余标的。
    unpriced_symbols: list[str] = field(default_factory=list)
    #: 这些标的的成本合计，供提示行说明「没算进去的是多少」。
    unpriced_cost: float = 0.0


def get_summary(db_path: str, group: str | None = None) -> PortfolioSummary:
    """计算持仓汇总，不输出任何文字。"""
    transactions = transaction_dao.get_all(db_path, group=group)
    positions = calculator.compute_positions(transactions)

    # 资产类型映射（用于配置占比）
    asset_types = {t.symbol: t.asset_type.value for t in transactions}

    # 含费用汇总（成本是账本事实，与有没有行情无关）
    total_fees = calculator.summarize(positions)["total_fees"]

    # 标的名称。一次取全表而不是逐条 get（N+1），取不到就回落到代码——
    # 名称是用来认人的，没有名字时代码本身就是最好的名字。
    names = {m.symbol: (m.name or m.symbol) for m in asset_meta_dao.get_all(db_path)}

    holdings_rows = []
    market_values: dict[str, float] = {}
    unpriced_symbols: list[str] = []
    priced_cost = 0.0
    unpriced_cost = 0.0
    for symbol, pos in positions.items():
        if pos.quantity <= 0:
            continue
        cached = price_cache_dao.get(db_path, symbol)
        # 没有缓存价就是「不知道」，不是 0——见 calculator.Holding 的说明。
        current_price = cached.price if cached else None
        h = calculator.holding_for(pos, current_price)
        holdings_rows.append(
            {
                "symbol": h.symbol,
                "name": names.get(symbol, symbol),
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
        if current_price is None:
            unpriced_symbols.append(symbol)
            unpriced_cost += pos.total_cost
        else:
            priced_cost += pos.total_cost
            market_values[symbol] = h.market_value

    holdings_df = pd.DataFrame(holdings_rows)
    total_value = sum(market_values.values())

    if unpriced_symbols and not market_values:
        # 一个标的有行情都没有：盈亏不是 0，是未知。印 0.00 只会是第二个
        # 「看着像结论」的假数字。
        total_profit: float | None = None
        profit_rate: float | None = None
    else:
        # pandas 的 sum 跳过 NaN，正好等于「有行情那些标的的盈亏合计」。
        total_profit = float(holdings_df["profit"].sum()) if not holdings_df.empty else 0.0
        # 分母只算有行情的成本：分子里的盈亏同样只含有行情的标的，
        # 两边口径不一致会算出一个既不是「全体」也不是「部分」的数。
        profit_rate = (total_profit / priced_cost * 100) if priced_cost else 0.0

    alloc = allocator.allocation_by_asset_type(market_values, asset_types)

    return PortfolioSummary(
        total_value=total_value,
        total_cost=priced_cost,
        total_profit=total_profit,
        profit_rate=profit_rate,
        total_fees=total_fees,
        allocation=alloc,
        holdings_df=holdings_df,
        fee_breakdown=calculator.fee_breakdown(transactions),
        unpriced_symbols=unpriced_symbols,
        unpriced_cost=unpriced_cost,
    )


def _market_of(transactions, symbol: str) -> str:
    for t in transactions:
        if t.symbol == symbol:
            return t.market.value
    return MarketType.A_SHARE.value
