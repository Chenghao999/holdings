"""holdings tui 命令：启动终端界面。

命令在这里，界面本体在 `holdings/tui/`——两者是平级的表现层，都只经 `services/`
取数。这样 CLI 与 TUI 可以各自演进，也不会互相 import。
"""

from __future__ import annotations

import click


@click.command()
def tui_cmd() -> None:
    """启动终端界面（持仓与报表两屏）。"""
    from holdings.utils.config import load_config

    try:
        from holdings.tui.app import HoldingsApp
    except ImportError as exc:
        # Textual 是可选依赖。缺了要按「缺依赖」的契约报（退出码 6），
        # 而不是漏一个 ImportError 出去——那会绕过 main() 的映射层。
        from holdings.exceptions import MissingDependencyError

        raise MissingDependencyError(
            "未安装 textual，无法启动界面；请运行 pip install 'holdings-cli[tui]'"
        ) from exc

    HoldingsApp(load_config().database_path).run()
