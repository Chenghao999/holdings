"""CLI 主入口：click 命令组，统一错误处理与退出码。"""

from __future__ import annotations

import click

from holdings.cli.commands.add import add
from holdings.cli.commands.chart import chart_cmd
from holdings.cli.commands.check import check_cmd
from holdings.cli.commands.import_cmd import import_cmd
from holdings.cli.commands.init import init
from holdings.cli.commands.list import list_cmd
from holdings.cli.commands.remove import remove_cmd
from holdings.cli.commands.report import report_cmd
from holdings.cli.commands.snapshot import snapshot_cmd
from holdings.cli.commands.sync import sync_cmd


@click.group()
@click.version_option(package_name="holdings")
def cli() -> None:
    """holdings —— 个人投资持仓追踪工具。"""


cli.add_command(init)
cli.add_command(add)
cli.add_command(check_cmd, name="check")
cli.add_command(list_cmd, name="list")
cli.add_command(import_cmd, name="import")
cli.add_command(sync_cmd, name="sync")
cli.add_command(report_cmd, name="report")
cli.add_command(snapshot_cmd, name="snapshot")
cli.add_command(chart_cmd, name="chart")
cli.add_command(remove_cmd, name="remove")


def main() -> None:
    """带异常->退出码映射的入口。"""
    from holdings.data.fetcher import DataSourceUnavailableError, SymbolNotFoundError
    from holdings.storage.db import DatabaseError
    from holdings.utils.config import ConfigError

    try:
        cli()
    # 异常已在上面转成友好提示，退出时不必再链上原始 traceback，故用 `from None`。
    except DataSourceUnavailableError as exc:
        click.echo(f"错误（1）：{exc}", err=True)
        raise SystemExit(1) from None
    except SymbolNotFoundError as exc:
        click.echo(f"错误（2）：{exc}", err=True)
        raise SystemExit(2) from None
    except ConfigError as exc:
        click.echo(f"错误（3）：{exc}", err=True)
        raise SystemExit(3) from None
    except DatabaseError as exc:
        click.echo(f"错误（4）：{exc}", err=True)
        raise SystemExit(4) from None


if __name__ == "__main__":
    main()
