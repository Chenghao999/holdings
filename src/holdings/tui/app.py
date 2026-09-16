"""holdings 的终端界面：持仓与报表两屏。

数据全部来自 `services/`，一行 SQL、一个网络请求都没有——这正是
[B-15](../../../docs/BACKLOG.md) 说的「前置条件已具备」：核心层不许输出、
不许依赖终端库、依赖方向合规，都有用例守着。

Textual 是可选依赖（`pip install 'holdings[tui]'`），本模块只在真正启动界面时导入。
"""

from __future__ import annotations

from typing import ClassVar

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import DataTable, Footer, Header, Static, TabbedContent, TabPane

from holdings.services.portfolio_service import HOLDINGS_COLUMNS, get_summary
from holdings.services.report_service import get_performance
from holdings.utils.formatter import (
    UNKNOWN,
    format_money,
    format_number,
    format_percent,
    format_price,
    format_quantity,
    format_ratio,
)

#: 表格里不显示这两列：名称列会把它撑得很宽，类型在本工具里几乎不变。
_TABLE_COLUMNS = [c for c in HOLDINGS_COLUMNS if c not in {"name", "asset_type"}]


class HoldingsApp(App):
    """持仓与报表两屏。`q` 退出，`r` 刷新。"""

    TITLE = "holdings"
    BINDINGS: ClassVar = [("q", "quit", "退出"), ("r", "refresh", "刷新")]

    def __init__(self, db_path: str) -> None:
        super().__init__()
        self.db_path = db_path

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent("持仓", "报表"):
            with TabPane("持仓", id="tab-holdings"), VerticalScroll():
                yield DataTable(id="holdings", zebra_stripes=True)
                yield Static(id="summary")
            with TabPane("报表", id="tab-report"), VerticalScroll():
                yield Static(id="report")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#holdings", DataTable)
        table.cursor_type = "row"
        table.add_columns(*(HOLDINGS_COLUMNS[c] for c in _TABLE_COLUMNS))
        self.refresh_data()

    def action_refresh(self) -> None:
        self.refresh_data()

    def refresh_data(self) -> None:
        """从服务层取数并填表。没有任何计算——算都在服务层算完了。"""
        summary = get_summary(self.db_path)
        table = self.query_one("#holdings", DataTable)
        table.clear()
        for _, row in summary.holdings_df.iterrows():
            table.add_row(*(_cell(column, row) for column in _TABLE_COLUMNS))
        self.query_one("#summary", Static).update(_summary_text(summary))
        self.query_one("#report", Static).update(_report_text(self.db_path))


def _cell(column: str, row) -> str:
    value = row.get(column)
    if column in {"quantity"}:
        return format_quantity(value)
    if column in {"avg_cost", "current_price"}:
        return format_price(value)
    if column in {"market_value", "total_fees", "profit"}:
        return format_money(value)
    if column == "profit_rate":
        return format_percent(value)
    return str(value if value is not None else "")


def _summary_text(summary) -> str:
    """汇总行。口径与 CLI 一致：只覆盖有行情的标的。"""
    priced = summary.total_profit is not None
    value = format_money(summary.total_value) if priced else UNKNOWN
    cost = format_money(summary.total_cost) if priced else UNKNOWN
    profit = (
        UNKNOWN
        if not priced
        else f"{format_money(summary.total_profit)} ({format_percent(summary.profit_rate)})"
    )
    lines = [
        f"总市值 {value} | 总成本 {cost} | 总盈亏 {profit} | "
        f"累计费用 {format_money(summary.total_fees)}"
    ]
    if summary.unpriced_symbols:
        lines.append(
            f"[yellow]{len(summary.unpriced_symbols)} 个标的无行情"
            f"（成本合计 {format_money(summary.unpriced_cost)}），未计入上面的汇总；"
            f"请先执行 holdings sync[/yellow]"
        )
    return "\n".join(lines)


def _report_text(db_path: str) -> str:
    """报表屏：绩效指标。措辞与 CLI 的绩效行保持同一套口径。"""
    perf = get_performance(db_path)
    if perf.snapshot_count < 2:
        return f"绩效：快照不足（当前 {perf.snapshot_count} 条，至少 2 条）"
    lines = [
        f"绩效（{perf.snapshot_count} 条快照，{perf.first_date} ~ {perf.last_date}）",
        f"  最大回撤 {format_ratio(perf.max_drawdown)}",
        f"  年化收益 {format_ratio(perf.annualized_return)}",
        f"  夏普     {format_number(perf.sharpe)}",
    ]
    lines.extend(f"  · {note}" for note in perf.notes)
    return "\n".join(lines)
