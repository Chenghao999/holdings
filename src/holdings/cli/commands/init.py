"""holdings init 命令。"""

from __future__ import annotations

import click


@click.command()
@click.option("--dev", is_flag=True, help="初始化开发/测试环境")
@click.pass_context
def init(ctx: click.Context, dev: bool) -> None:
    """初始化项目：创建数据库与默认配置文件。"""
    from holdings.storage.db import connect
    from holdings.utils.config import load_config

    cfg = load_config()
    connect(cfg.database_path)
    # 首次加载配置文件由 load_config 自动用默认值，不落盘；这里显式写出
    if not cfg._path.exists():
        cfg.save()
    click.echo(f"已初始化数据库：{cfg.database_path}")

    # 依赖体检：缺失必需依赖时提示（不阻断初始化，仅提示）
    from holdings.utils.deps import missing_required

    missing = missing_required()
    if missing:
        click.echo(f"警告：缺少必需依赖 {', '.join(missing)}，请运行 `pip install -e .`", err=True)

    if dev:
        click.echo("开发模式已启用（暂不创建额外数据）")
