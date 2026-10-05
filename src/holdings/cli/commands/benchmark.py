"""holdings benchmark 命令：组合与基准指数的同期收益对比。"""

from __future__ import annotations

from datetime import date

import click

from holdings.cli.dates import optional


@click.command()
@click.option(
    "--against",
    required=True,
    help="基准：沪深300 / 中证500 / 上证指数 / 标普500 / 纳斯达克，或指数代码",
)
@click.option(
    "--start",
    default=None,
    callback=optional,
    help="起始日期 YYYY-MM-DD，只用该日（含）之后的快照",
)
def benchmark_cmd(against: str, start: date | None) -> None:
    """把组合的时间加权收益与基准指数摆在一起。"""
    from holdings.cli.renderers.table_renderer import render_benchmark_line
    from holdings.services.benchmark_service import get_benchmark
    from holdings.utils.config import load_config

    cfg = load_config()
    result = get_benchmark(
        cfg.database_path,
        against,
        start=start,
        ttl_seconds=cfg.history_ttl_seconds,
        # `sync.timeout_seconds` 是**全项目唯一那个「一次网络调用等多久」的旋钮**
        # （`sync` 也是这么传的）。不传的话，用户为慢网络调大了它，
        # `benchmark` 却还在按写死的 10 秒放弃——报出来的是一句「拉取超时」，
        # 而真正的原因（这个源本来就慢）被那句话盖住了。真跑一次才发现的。
        timeout_seconds=cfg.sync_timeout_seconds,
    )
    click.echo(render_benchmark_line(result))
