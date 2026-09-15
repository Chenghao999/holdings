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
        render_performance_line,
        render_summary_line,
        render_unpriced_hint,
    )
    from holdings.services.portfolio_service import get_summary
    from holdings.services.report_service import get_performance
    from holdings.utils.config import load_config

    cfg = load_config()
    summary = get_summary(cfg.database_path)
    performance = get_performance(cfg.database_path)

    console = Console()
    console.print(render_holdings_table(summary.holdings_df))
    console.print(render_summary_line(summary))
    hint = render_unpriced_hint(summary)
    if hint:
        console.print(f"[yellow]{hint}[/yellow]")
    # 绩效来自 snapshots（用户手记），与上面的持仓汇总（来自交易流水）是两条数据源，
    # 没有记过快照时它整行都是 `—`，这很正常，不是错误。
    console.print(render_performance_line(performance))

    if verbose:
        console.print(render_fee_table(summary.fee_breakdown))
        console.print(render_allocation_table(summary.allocation))
