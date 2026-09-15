"""将持仓 DataFrame 转为 Rich 表格。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.table import Table

if TYPE_CHECKING:
    from holdings.services.report_service import PerformanceSummary

# 指标口径不成立时统一显示这个，而不是 0——「回撤 0.00%」看着像结论，
# 「—」才是「这条数据算不出来」的诚实写法。
_UNKNOWN = "—"


def _percent(value: float | None) -> str:
    return _UNKNOWN if value is None else f"{value * 100:.2f}%"


def _number(value: float | None) -> str:
    return _UNKNOWN if value is None else f"{value:.2f}"


def render_performance_line(perf: PerformanceSummary) -> str:
    """把绩效指标渲染成一行文本；出现 `—` 时另起一行说明原因。

    说明为什么要有那一行：`夏普 —` 单独出现时，用户分不清是「程序坏了」
    还是「这组数据算不出夏普」。原因由 service 给出，渲染层只负责排版。
    """
    if perf.snapshot_count < 2:
        return (
            f"绩效：快照不足（当前 {perf.snapshot_count} 条，至少 2 条），"
            f"回撤 / 年化 / 夏普均不可计算"
        )
    line = (
        f"绩效（{perf.snapshot_count} 条快照，{perf.first_date} ~ {perf.last_date}）："
        f"最大回撤 {_percent(perf.max_drawdown)} | "
        f"年化收益 {_percent(perf.annualized_return)} | "
        f"夏普 {_number(perf.sharpe)}"
    )
    if perf.notes:
        line += "\n  " + "；".join(perf.notes)
    return line


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
