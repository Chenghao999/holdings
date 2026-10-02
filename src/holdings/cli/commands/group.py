"""holdings group 命令：管理组合（列出 / 改名 / 合并）。

组合作是筛选标签存在了很久——`add` / `import` / `list --group` 都认它，
却没有任何地方能看有哪些组合、改名或合并：名字写错一次就永久留在库里，
想把两个组合并起来只能手动改 SQLite。这条命令补上这个入口。

三条子命令归在一个子命令组里（而其余命令都是平铺的）：它们是同一件事的
三个动词，平铺成 `groups` / `group-rename` / `group-merge` 只会让 `--help`
更长，还读不出彼此的关系。
"""

from __future__ import annotations

import click


@click.group()
def group_cmd() -> None:
    """管理组合（账户分组）。"""


@group_cmd.command("list")
def list_groups_cmd() -> None:
    """列出全部组合及其总市值 / 盈亏。"""
    from rich.console import Console

    from holdings.cli.renderers.table_renderer import render_group_hints, render_groups_table
    from holdings.services import group_service
    from holdings.utils.config import load_config

    cfg = load_config()
    rows = group_service.list_groups(cfg.database_path)

    console = Console()
    console.print(render_groups_table(rows))
    # 提示句子由服务层给（与 `list` / `report` 同一份），这里只负责上色。
    for row in rows:
        for hint in render_group_hints(row):
            console.print(f"[yellow]{hint}[/yellow]")


@group_cmd.command("rename")
@click.argument("old")
@click.argument("new")
def rename_cmd(old: str, new: str) -> None:
    """把组合 OLD 改名为 NEW。"""
    from holdings.services import group_service
    from holdings.utils.config import load_config

    cfg = load_config()
    moved = group_service.rename_group(cfg.database_path, old, new)

    if moved == 0:
        click.echo("组合名未变，未做任何改动")
        return
    old, new = old.strip(), new.strip()
    click.echo(f"已把 {moved} 笔交易从『{old}』改名为『{new}』")
    click.echo(f"查看：holdings list --group {new}")
    if old == cfg.default_group:
        click.echo(group_service.default_group_note(old))


@group_cmd.command("merge")
@click.argument("source")
@click.argument("target")
def merge_cmd(source: str, target: str) -> None:
    """把组合 SOURCE 的交易全部并入 TARGET，SOURCE 之后不再存在。"""
    from holdings.services import group_service
    from holdings.utils.config import load_config

    cfg = load_config()
    moved = group_service.merge_groups(cfg.database_path, source, target)

    source, target = source.strip(), target.strip()
    click.echo(f"已把『{source}』的 {moved} 笔交易并入『{target}』；『{source}』不再存在")
    click.echo(f"查看：holdings list --group {target}")
    if source == cfg.default_group:
        click.echo(group_service.default_group_note(source))
