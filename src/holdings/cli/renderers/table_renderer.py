"""将持仓 DataFrame 转为 Rich 表格。"""

from __future__ import annotations

from rich.table import Table


def render_holdings_table(holdings_df) -> Table:
    """根据持仓明细 DataFrame 渲染表格。"""
    table = Table(title="持仓明细")
    if holdings_df.empty:
        table.add_column("提示")
        table.add_row("暂无持仓")
        return table

    columns = {
        "symbol": "代码",
        "market": "市场",
        "asset_type": "类型",
        "quantity": "数量",
        "avg_cost": "成本价",
        "current_price": "现价",
        "market_value": "市值",
        "total_fees": "累计费用",
        "profit": "盈亏",
        "profit_rate": "盈亏率",
    }
    for label in columns.values():
        table.add_column(label, justify="right")

    for _, row in holdings_df.iterrows():
        table.add_row(
            str(row.get("symbol", "")),
            str(row.get("market", "")),
            str(row.get("asset_type", "")),
            f"{row.get('quantity', 0):.4f}",
            f"{row.get('avg_cost', 0):.4f}",
            f"{row.get('current_price', 0):.4f}",
            f"{row.get('market_value', 0):,.2f}",
            f"{row.get('total_fees', 0):,.4f}",
            f"{row.get('profit', 0):,.2f}",
            f"{row.get('profit_rate', 0):.2f}%",
        )
    return table


def render_fee_table(fee_breakdown: dict) -> Table:
    """渲染费用分项表。"""
    table = Table(title="费用分项")
    table.add_column("代码", justify="left")
    table.add_column("费用金额", justify="right")
    if not fee_breakdown:
        table.add_row("无", "0.00")
        return table
    for symbol, amount in fee_breakdown.items():
        table.add_row(symbol, f"{amount:,.4f}")
    return table


def render_allocation_table(allocation: dict) -> Table:
    """渲染配置占比表。"""
    table = Table(title="资产配置占比")
    table.add_column("资产类型", justify="left")
    table.add_column("占比", justify="right")
    if not allocation:
        table.add_row("无", "0.00%")
        return table
    for atype, ratio in allocation.items():
        table.add_row(atype, f"{ratio * 100:.2f}%")
    return table
