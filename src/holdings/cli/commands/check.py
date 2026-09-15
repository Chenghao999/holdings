"""holdings check 命令：检查依赖包是否安装。"""

from __future__ import annotations

import click


@click.command()
@click.option("--json", "as_json", is_flag=True, help="以 JSON 输出结果")
def check_cmd(as_json: bool) -> None:
    """检查运行环境依赖是否齐全。"""
    from holdings.utils.deps import check_dependencies, missing_required

    statuses = check_dependencies()

    if as_json:
        import json

        click.echo(
            json.dumps(
                [
                    {
                        "package": s.package_name,
                        "installed": s.installed,
                        "required": s.required,
                        "purpose": s.purpose,
                    }
                    for s in statuses
                ],
                ensure_ascii=False,
            )
        )
        return

    from rich.console import Console
    from rich.table import Table

    table = Table(title="依赖检查")
    table.add_column("包名", justify="left")
    table.add_column("类别", justify="left")
    table.add_column("状态", justify="left")

    for s in statuses:
        label = "必需" if s.required else f"可选（{s.purpose}）"
        if s.installed:
            table.add_row(s.package_name, label, "[green]已安装[/green]")
        elif s.required:
            table.add_row(s.package_name, label, "[red]缺失[/red]")
        else:
            table.add_row(s.package_name, label, "[yellow]未安装[/yellow]")

    console = Console()
    console.print(table)

    missing = missing_required()
    if missing:
        console.print(f"[red]缺少必需依赖：{', '.join(missing)}[/red]")
        console.print("请运行：pip install -e .")
        raise SystemExit(1)
    console.print("[green]必需依赖齐全。[/green]")
