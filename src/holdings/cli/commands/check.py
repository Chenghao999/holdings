"""holdings check 命令：检查依赖包是否安装。"""

from __future__ import annotations

import click


@click.command()
@click.option("--json", "as_json", is_flag=True, help="以 JSON 输出结果")
def check_cmd(as_json: bool) -> None:
    """检查运行环境依赖是否齐全。"""
    from holdings.utils.deps import check_dependencies, missing_required

    statuses = check_dependencies()
    # 先算结果、再输出、最后才决定退出码。此前 as_json 分支在检查之前就 return，
    # 缺依赖时仍退出 0——靠退出码判断的 CI 脚本会漏检，这是 B-08 里唯一会真咬人的。
    missing = missing_required()

    if as_json:
        import json

        click.echo(
            json.dumps(
                {
                    # 给脚本一个能直接判断的字段，不必去翻 packages 数组。
                    "ok": not missing,
                    "missing_required": missing,
                    "packages": [
                        {
                            "package": s.package_name,
                            "installed": s.installed,
                            "required": s.required,
                            "purpose": s.purpose,
                        }
                        for s in statuses
                    ],
                },
                ensure_ascii=False,
            )
        )
        _fail_if_missing(missing)
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

    if missing:
        _fail_if_missing(missing)
    console.print("[green]必需依赖齐全。[/green]")


def _fail_if_missing(missing: list[str]) -> None:
    """缺必需依赖就抛出去，由 main() 统一成「错误（6）：…」。

    文本模式与 `--json` 模式共用这一条出口，两种模式的退出码因此不可能不一致。
    """
    if not missing:
        return
    from holdings.exceptions import MissingDependencyError

    raise MissingDependencyError(f"缺少必需依赖：{'、'.join(missing)}；请运行：pip install -e .")
