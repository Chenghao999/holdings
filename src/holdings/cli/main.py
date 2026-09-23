"""CLI 主入口：click 命令组，统一错误处理与退出码。"""

from __future__ import annotations

import click

from holdings.cli.commands.add import add
from holdings.cli.commands.chart import chart_cmd
from holdings.cli.commands.check import check_cmd
from holdings.cli.commands.import_cmd import import_cmd
from holdings.cli.commands.init import init
from holdings.cli.commands.list import list_cmd
from holdings.cli.commands.meta import meta_cmd
from holdings.cli.commands.remove import remove_cmd
from holdings.cli.commands.report import report_cmd
from holdings.cli.commands.snapshot import snapshot_cmd
from holdings.cli.commands.snapshots import snapshots_cmd
from holdings.cli.commands.sync import sync_cmd
from holdings.cli.commands.tui import tui_cmd
from holdings.cli.commands.web import web_cmd


@click.group()
@click.version_option(package_name="holdings-cli")
def cli() -> None:
    """holdings —— 个人投资持仓追踪工具。"""


cli.add_command(init)
cli.add_command(add)
cli.add_command(check_cmd, name="check")
cli.add_command(list_cmd, name="list")
cli.add_command(meta_cmd, name="meta")
cli.add_command(import_cmd, name="import")
cli.add_command(sync_cmd, name="sync")
cli.add_command(report_cmd, name="report")
cli.add_command(snapshot_cmd, name="snapshot")
cli.add_command(snapshots_cmd, name="snapshots")
cli.add_command(chart_cmd, name="chart")
cli.add_command(tui_cmd, name="tui")
cli.add_command(web_cmd, name="web")
cli.add_command(remove_cmd, name="remove")


def exit_code_for(exc: BaseException, default: int = 1) -> int:
    """异常 → 退出码。契约见 docs/ERROR_HANDLING.md。

    映射表放在模块级而不是 `main()` 里：测试要断言的是这张表本身，
    藏在函数体里就只能靠「跑一遍命令看退出码」间接验证——那样每加一条
    分支都要跑一次完整的 CLI，而漏加的映射反而不会被发现。
    """
    from holdings.exceptions import (
        ConfigError,
        DatabaseError,
        DataSourceUnavailableError,
        MissingDependencyError,
        RecordNotFoundError,
        SymbolNotFoundError,
        TradeValidationError,
    )

    #: 「缺少依赖」单独占一个码：它与「网络不通」是两种完全不同的处置——
    #: 前者要装包（重试多少次都没用），后者才值得重试。CI 里靠退出码分流时，
    #: 把这两种故障并到同一个 1 会让「网络抖动」和「环境没装好」看起来一样。
    mapping: tuple[tuple[type[BaseException], int], ...] = (
        (MissingDependencyError, 6),
        (DataSourceUnavailableError, 1),
        (SymbolNotFoundError, 2),
        (RecordNotFoundError, 2),
        (ConfigError, 3),
        (DatabaseError, 4),
        (TradeValidationError, 5),
    )
    return next((code for exc_type, code in mapping if isinstance(exc, exc_type)), default)


def main() -> None:
    """带 异常→退出码 映射的入口，见 docs/ERROR_HANDLING.md。"""
    from holdings.exceptions import HoldingsError

    # standalone_mode=False 让 click 把用法错误抛出来而不是自己 exit(2)——
    # click 默认的 2 与「标的未找到」的 2 撞码，这里统一按文档归到 5。
    try:
        cli.main(standalone_mode=False)
    except click.UsageError as exc:
        click.echo(f"错误（5）：{exc.format_message()}", err=True)
        raise SystemExit(5) from None
    except click.Abort:
        # click.confirm 被拒时抛 Abort；退出码 130 是「被中断」的惯例。
        click.echo("已中止", err=True)
        raise SystemExit(130) from None
    # 异常已在上面转成友好提示，退出时不必再链上原始 traceback，故用 `from None`。
    except HoldingsError as exc:
        code = exit_code_for(exc)
        click.echo(f"错误（{code}）：{exc}", err=True)
        raise SystemExit(code) from None


if __name__ == "__main__":
    main()
