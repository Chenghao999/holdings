"""holdings list 命令。"""

from __future__ import annotations

import click

from holdings.services.portfolio_service import HOLDINGS_COLUMNS

# 表格里的列名是中文，DataFrame 的列名是英文，`--sort 盈亏率` 直接拿去和
# df.columns 比会永远不匹配——此前它不报错也不排序，静默失效。
# 中文表头既是对用户展示的名字，就让它成为对用户输入的名字。
# 别名表从渲染层那份列定义派生，两处不再各维护一份。
_SORT_ALIASES = {
    **{label: column for column, label in HOLDINGS_COLUMNS.items()},
    **{column: column for column in HOLDINGS_COLUMNS},
}
# 中英文都接受：中文是文档里的写法，英文列名保留给老脚本。
_SORT_CHOICES = [*_SORT_ALIASES, *_SORT_ALIASES.values()]


@click.command()
@click.option(
    "--sort",
    "sort_key",
    default=None,
    type=click.Choice(_SORT_CHOICES),
    help="排序字段（降序），如：盈亏率",
)
@click.option("--group", default=None, help="按组合筛选")
def list_cmd(sort_key: str | None, group: str | None) -> None:
    """查看当前持仓明细。"""
    from rich.console import Console

    from holdings.cli.renderers.table_renderer import (
        render_foreign_hint,
        render_holdings_table,
        render_summary_line,
        render_unpriced_hint,
    )
    from holdings.services.portfolio_service import get_summary
    from holdings.utils.config import load_config

    cfg = load_config()
    summary = get_summary(cfg.database_path, group=group)
    df = summary.holdings_df

    if sort_key:
        column = _SORT_ALIASES.get(sort_key, sort_key)
        if not df.empty:
            # na_position="last"：没有行情的标的排到末尾。否则按盈亏率降序时，
            # 它们会因为空值而混在中间甚至排到前面，把排序结果搅乱。
            df = df.sort_values(by=column, ascending=False, na_position="last")

    console = Console()
    console.print(render_holdings_table(df, width=console.width))
    console.print(render_summary_line(summary))
    # 两类没进汇总的标的各说各的：原因不同，用户要做的事也不同
    # （无行情去 sync，外币计价则只能等 v2.0.0 的汇率换算）。
    for hint in (render_unpriced_hint(summary), render_foreign_hint(summary)):
        if hint:
            console.print(f"[yellow]{hint}[/yellow]")
