"""holdings chart 命令：生成净值曲线图。"""

from __future__ import annotations

import click


@click.command()
@click.option("--output", default="networth.html", help="输出 HTML 文件路径")
@click.option("--start", default=None, help="起始日期 YYYY-MM-DD（暂存参数）")
def chart_cmd(output: str, start: str | None) -> None:
    """生成交互式净值曲线图。"""
    import webbrowser

    from holdings.cli.renderers.chart_renderer import write_html
    from holdings.services.chart_service import networth_figure
    from holdings.utils.config import load_config

    cfg = load_config()
    fig = networth_figure(cfg.database_path)
    write_html(fig, output)
    click.echo(f"已生成图表：{output}")
    webbrowser.open(output)
