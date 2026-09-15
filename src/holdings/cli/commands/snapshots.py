"""holdings snapshots 命令：列出已记录的快照。

与 `holdings snapshot`（记录一份）成对：那个写，这个看。
没有这个命令之前，`--note` 写了也没人看得见——数据落库了却读不出来，
与丢数据只差一步。
"""

from __future__ import annotations

import click


@click.command()
def snapshots_cmd() -> None:
    """列出已记录的快照与备注。"""
    from rich.console import Console

    from holdings.cli.renderers.table_renderer import render_snapshots_table
    from holdings.services import snapshot_service
    from holdings.utils.config import load_config

    cfg = load_config()
    console = Console()
    console.print(render_snapshots_table(snapshot_service.list_all(cfg.database_path)))
