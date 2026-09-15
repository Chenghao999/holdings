"""holdings report 命令。"""

from __future__ import annotations

import click


@click.command()
@click.option("--verbose", is_flag=True, help="显示费用分项与配置占比")
def report_cmd(verbose: bool) -> None:
    """生成综合报表。"""
    from rich.console import Console

    from holdings.cli.renderers.table_renderer import (
        render_allocation_table,
        render_fee_table,
        render_holdings_table,
    )
    from holdings.services.portfolio_service import get_summary
    from holdings.utils.config import load_config

    cfg = load_config()
    summary = get_summary(cfg.database_path)

    console = Console()
    console.print(render_holdings_table(summary.holdings_df))
    console.print(
        f"总市值 {summary.total_value:,.2f} | "
        f"总成本 {summary.total_cost:,.2f} | "
        f"总盈亏 {summary.total_profit:,.2f} ({summary.profit_rate:.2f}%) | "
        f"累计费用 {summary.total_fees:,.2f}"
    )

    if verbose:
        console.print(render_fee_table(summary.fee_breakdown))
        console.print(render_allocation_table(summary.allocation))
