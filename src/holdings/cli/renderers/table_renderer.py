"""将持仓 DataFrame 转为 Rich 表格。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.table import Table

from holdings.services.portfolio_service import BASE_CURRENCY, HOLDINGS_COLUMNS
from holdings.utils.formatter import (
    UNKNOWN,
    format_money,
    format_number,
    format_percent,
    format_price,
    format_quantity,
    format_ratio,
)

if TYPE_CHECKING:
    from holdings.services.portfolio_service import PortfolioSummary
    from holdings.services.report_service import PerformanceSummary

# 指标口径不成立时统一显示这个，而不是 0——「回撤 0.00%」看着像结论，
# 「—」才是「这条数据算不出来」的诚实写法。
_UNKNOWN = "—"

#: 窄于这个宽度就只渲染简表。80 列是终端的默认宽度，而持仓表有 10 列——
#: 放不下时 Rich 会平均截断每一列，代码列只剩 `6005…`，用户认不出自己持的是
#: 什么。10 列本来也不是窄终端能承载的信息量，与其每列都看不清，不如只显示
#: 真正要看的那几列。
COMPACT_WIDTH_THRESHOLD = 100

#: 简表显示的列：持的是什么、多少、现价、赚不赚。
COMPACT_COLUMNS = ("symbol", "quantity", "current_price", "profit_rate")

#: 标识列：这些列被截断就等于信息没了，所以设 no_wrap 并给出最小宽度，
#: 让 Rich 优先牺牲数字列——数字被截断至少还能一眼看出是「某个数」。
_IDENTIFIER_COLUMNS = {"symbol": 6, "market": 2, "asset_type": 4}


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
        f"最大回撤 {format_ratio(perf.max_drawdown)} | "
        f"年化收益 {format_ratio(perf.annualized_return)} | "
        f"夏普 {format_number(perf.sharpe)}"
    )
    if perf.notes:
        line += "\n  " + "；".join(perf.notes)
    return line


def render_holdings_table(holdings_df, width: int | None = None) -> Table:
    """根据持仓明细 DataFrame 渲染表格。

    `width` 是终端宽度。窄于 `COMPACT_WIDTH_THRESHOLD` 时只渲染
    `COMPACT_COLUMNS` 四列，理由是 10 列在 80 列终端里只能平均截断，
    结果是代码列也认不出来——那比少显示几列更糟。
    传 `None` 表示按全表渲染（测试与窄宽无关的调用方走这条）。
    """
    table = Table(title="持仓明细")
    if holdings_df.empty:
        table.add_column("提示")
        table.add_row("暂无持仓")
        return table

    columns = HOLDINGS_COLUMNS
    compact = width is not None and width < COMPACT_WIDTH_THRESHOLD
    shown = [c for c in columns if not compact or c in COMPACT_COLUMNS]
    for column in shown:
        table.add_column(
            columns[column],
            justify="right",
            no_wrap=column in _IDENTIFIER_COLUMNS,
            min_width=_IDENTIFIER_COLUMNS.get(column),
        )

    for _, row in holdings_df.iterrows():
        if compact:
            table.add_row(*_compact_cells(row))
            continue
        table.add_row(
            str(row.get("symbol", "")),
            str(row.get("name", row.get("symbol", ""))),
            str(row.get("market", "")),
            str(row.get("asset_type", "")),
            format_quantity(row.get("quantity")),
            format_price(row.get("avg_cost")),
            _price_cell(row),
            # 市值 / 盈亏 / 盈亏率：算不出来时 service 给的是 NaN 而不是 0，
            # `format_money` 把它显示成 `—`。按 0 显示会让盈亏率变成「−100.00%」，
            # 那是没同步过，不是血亏；外币计价的标的走同一条路——数字是真的，
            # 但不是人民币口径，放不进这一列。
            format_money(row.get("market_value")),
            format_money(row.get("total_fees")),
            format_money(row.get("profit")),
            format_percent(row.get("profit_rate")),
        )
    return table


def _compact_cells(row) -> list[str]:
    """简表的四个单元格，与 `COMPACT_COLUMNS` 一一对应。"""
    return [
        str(row.get("symbol", "")),
        format_quantity(row.get("quantity")),
        _price_cell(row),
        format_percent(row.get("profit_rate")),
    ]


def _price_cell(row) -> str:
    """现价，外币的带上币种。

    同一列里混着两种货币而不加标注，等于把「不混加」这件事做了一半：
    用户看到的仍是一个没有单位的数。非基准货币才标——每行都挂一个 `CNY`
    只会把这一列撑宽，而人民币是本工具的默认口径。
    """
    price = format_price(row.get("current_price"))
    currency = row.get("currency")
    # `isinstance` 而不是判空：DataFrame 里的缺失值可能是 `None`，也可能是 NaN。
    if not isinstance(currency, str) or currency == BASE_CURRENCY:
        return price
    return f"{price} {currency}"


def render_fee_table(fee_breakdown: dict) -> Table:
    """渲染费用分项表。"""
    table = Table(title="费用分项")
    table.add_column("代码", justify="left")
    table.add_column("费用金额", justify="right")
    if not fee_breakdown:
        table.add_row("无", "0.00")
        return table
    for symbol, amount in fee_breakdown.items():
        table.add_row(symbol, format_money(amount))
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
        table.add_row(atype, format_ratio(ratio))
    return table


def render_snapshots_table(snapshots) -> Table:
    """渲染快照列表。

    `note` 为空时留白，不印「—」：备注是可选信息，一片「—」反而像出了错。
    """
    table = Table(title="资产快照")
    table.add_column("日期", justify="left")
    table.add_column("总资产", justify="right")
    table.add_column("权益", justify="right")
    table.add_column("黄金", justify="right")
    table.add_column("现金", justify="right")
    table.add_column("备注", justify="left")
    if not snapshots:
        table.add_row("暂无快照", "", "", "", "", "用 holdings snapshot 记录一份")
        return table
    for s in snapshots:
        table.add_row(
            s.snapshot_date.isoformat(),
            format_money(s.total_value),
            format_money(s.equity_value),
            format_money(s.gold_value),
            format_money(s.cash_balance),
            s.note or "",
        )
    return table


def render_summary_line(summary: PortfolioSummary) -> str:
    """持仓汇总行。口径是**能按基准货币计价的标的**，没算进去的由提示行说明。

    一个标的都计不进来时不再印 `0.00`：那会让「总市值 0 / 总成本 0 / 总盈亏 0」
    看起来像空仓，而实际是持有着、只是没法按人民币说清楚。service 在那种情况下
    给的就是 `None`，`format_money` 把它显示成 `—`，渲染层不必自己判断。
    """
    profit = (
        UNKNOWN
        if summary.total_profit is None
        else f"{format_money(summary.total_profit)} ({format_percent(summary.profit_rate)})"
    )
    return (
        f"总市值 {format_money(summary.total_value)} | "
        f"总成本 {format_money(summary.total_cost)} | "
        f"总盈亏 {profit} | 累计费用 {summary.total_fees:,.2f}"
    )


def render_fee_rate_line(rate: float) -> str | None:
    """年化管理费率合计。费率为 0 时返回 None——没填过就别印一行废话。

    措辞必须让用户明白它**没被计进成本**：它旁边就是「累计费用」，
    不加这句很容易被读成「总费用又多了这么多」。
    """
    if not rate:
        return None
    return f"年化管理费率合计 {rate:g}%（仅供参考，未计入成本）"
