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
        render_fee_rate_line,
        render_fee_table,
        render_holdings_table,
        render_performance_line,
        render_summary_line,
    )
    from holdings.services import asset_meta_service
    from holdings.services.portfolio_service import foreign_hint, get_summary, unpriced_hint
    from holdings.services.report_service import get_performance
    from holdings.utils.config import load_config

    cfg = load_config()
    summary = get_summary(cfg.database_path)
    performance = get_performance(cfg.database_path)

    console = Console()
    console.print(render_holdings_table(summary.holdings_df, width=console.width))
    console.print(render_summary_line(summary))
    # 句子由服务层给（与 Web 看板同一份），这里只负责上色。
    for hint in (unpriced_hint(summary), foreign_hint(summary)):
        if hint:
            console.print(f"[yellow]{hint}[/yellow]")
    # 年化管理费率只是「你填过的费率加起来是多少」，与上面的累计费用不是一回事。
    symbols = [] if summary.holdings_df.empty else summary.holdings_df["symbol"].tolist()
    fee_line = render_fee_rate_line(asset_meta_service.fee_rate_total(cfg.database_path, symbols))
    if fee_line:
        console.print(fee_line)

    # 绩效来自 snapshots（用户手记），与上面的持仓汇总（来自交易流水）是两条数据源，
    # 没有记过快照时它整行都是 `—`，这很正常，不是错误。
    console.print(render_performance_line(performance))

    if verbose:
        console.print(render_fee_table(summary.fee_breakdown))
        console.print(render_allocation_table(summary.allocation))
