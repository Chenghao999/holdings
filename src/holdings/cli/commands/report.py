"""holdings report 命令。"""

from __future__ import annotations

import click


@click.command()
@click.option("--verbose", is_flag=True, help="显示费用分项与配置占比")
@click.option("--group", default=None, help="只看某个组合，与 holdings list --group 一致")
@click.option("--by-group", "by_group", is_flag=True, help="按组合分组展示，每个组合一块")
def report_cmd(
    verbose: bool = False,
    group: str | None = None,
    by_group: bool = False,
) -> None:
    """生成综合报表。

    三个参数都带 Python 默认值：click 只在真正解析命令行时补默认值，直接调用
    `report_cmd.callback()` 的地方（用例）拿到的就是签名本身，缺默认值会 TypeError。
    """
    from rich.console import Console

    from holdings.cli.renderers.table_renderer import render_performance_line
    from holdings.services import group_service, report_service
    from holdings.utils.config import load_config

    if by_group and group:
        # 一个说「只看这一组」，一个说「每组都看」，同时给没有合理语义。
        raise click.UsageError("--by-group 与 --group 不能同时使用")

    cfg = load_config()
    console = Console()

    if by_group:
        rows = group_service.list_groups(cfg.database_path)
        if not rows:
            console.print("暂无组合")
        for row in rows:
            console.rule(f"组合：{row.group}")
            # 汇总已经在 group_service 里算过，直接复用——再算一次只是多一次读，
            # 还给了两处数字走样的机会。
            _render_one(console, cfg.database_path, row.group, verbose, summary=row.summary)
    else:
        _render_one(console, cfg.database_path, group, verbose)

    # 绩效来自 snapshots（用户手记），与上面的持仓汇总（来自交易流水）是两条数据源，
    # 没有记过快照时它整行都是 `—`，这很正常，不是错误。
    # 快照没有组合字段，所以不论分不分组，它都只能是整份组合的绩效。
    console.print(render_performance_line(report_service.get_performance(cfg.database_path)))
    if by_group:
        console.print(f"[dim]{report_service.PERFORMANCE_SCOPE_NOTE}[/dim]")


def _render_one(console, db_path: str, group: str | None, verbose: bool, summary=None) -> None:
    """印一块「持仓表 + 汇总行 + 口径提示 + 费率行」；`verbose` 时再加两张分项表。

    默认、`--group`、`--by-group` 的每一轮共用这一处：分组展示最容易出的问题
    是某一组少了一行、或几处口径慢慢走开，而这三种模式的差别只在「算哪一组」。
    """
    from holdings.cli.renderers.table_renderer import (
        render_allocation_table,
        render_fee_rate_line,
        render_fee_table,
        render_holdings_table,
        render_summary_line,
    )
    from holdings.services import asset_meta_service
    from holdings.services.portfolio_service import foreign_hint, get_summary, unpriced_hint

    if summary is None:
        summary = get_summary(db_path, group=group)

    console.print(render_holdings_table(summary.holdings_df, width=console.width))
    console.print(render_summary_line(summary))
    # 句子由服务层给（与 Web 看板同一份），这里只负责上色。
    for hint in (unpriced_hint(summary), foreign_hint(summary)):
        if hint:
            console.print(f"[yellow]{hint}[/yellow]")
    # 年化管理费率只是「你填过的费率加起来是多少」，与上面的累计费用不是一回事。
    symbols = [] if summary.holdings_df.empty else summary.holdings_df["symbol"].tolist()
    fee_line = render_fee_rate_line(asset_meta_service.fee_rate_total(db_path, symbols))
    if fee_line:
        console.print(fee_line)

    if verbose:
        console.print(render_fee_table(summary.fee_breakdown))
        console.print(render_allocation_table(summary.allocation))
