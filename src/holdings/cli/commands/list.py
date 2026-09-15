"""holdings list 命令。"""

from __future__ import annotations

import click


@click.command()
@click.option("--sort", "sort_key", default=None, help="排序字段，如：盈亏率")
@click.option("--group", default=None, help="按组合筛选")
def list_cmd(sort_key: str | None, group: str | None) -> None:
    """查看当前持仓明细。"""
    from rich.console import Console

    from holdings.cli.renderers.table_renderer import render_holdings_table
    from holdings.services.portfolio_service import get_summary
    from holdings.utils.config import load_config

    cfg = load_config()
    summary = get_summary(cfg.database_path, group=group)
    df = summary.holdings_df

    if sort_key and not df.empty and sort_key in df.columns:
        df = df.sort_values(by=sort_key, ascending=False)

    console = Console()
    console.print(render_holdings_table(df))
    console.print(
        f"总市值 {summary.total_value:,.2f} | "
        f"总成本 {summary.total_cost:,.2f} | "
        f"总盈亏 {summary.total_profit:,.2f} ({summary.profit_rate:.2f}%) | "
        f"累计费用 {summary.total_fees:,.2f}"
    )
