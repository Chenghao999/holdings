"""holdings export 命令：把账本 / 持仓表 / 快照导出成文件。"""

from __future__ import annotations

import click

from holdings.cli.renderers.export_renderer import WRITERS
from holdings.services.export_service import BUILDERS


@click.command()
@click.option(
    "--what",
    type=click.Choice(list(BUILDERS)),
    default="ledger",
    show_default=True,
    help="导出什么：账本 / 持仓表 / 快照",
)
@click.option("--out", "out_path", required=True, help="输出文件路径")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(list(WRITERS)),
    default="csv",
    show_default=True,
    help="文件格式",
)
def export_cmd(what: str, out_path: str, fmt: str) -> None:
    """导出账本 / 持仓表 / 快照。

    **账本（默认那一种）能再导回来**：它用的是本工具自己的标准 CSV 表头，
    也就是 `holdings import` 认的那一份，所以备份与迁移走这一条——
    `holdings export --out ledger.csv`，换台机器 `holdings import --file ledger.csv`。
    数量与金额原样写出，不做四舍五入。

    持仓表与快照是给人看、给 Excel 用的，没有对应的导入路径。

    导出的 **CSV 带 BOM**（`utf-8-sig`），这样 Excel 双击打开中文不乱码；
    本工具自己的导入认得 BOM，所以带 BOM 的账本照样导得回来。

    `--out` 是必填的：三样东西共用一个默认文件名会互相覆盖。

    目标文件已存在时会**直接覆盖**——与 `holdings chart --output` 一致。
    """
    from holdings.cli.renderers import export_renderer
    from holdings.services import export_service
    from holdings.utils.config import load_config

    cfg = load_config()
    dataset = export_service.build(what, cfg.database_path)
    export_renderer.write(dataset, out_path, fmt)

    # 0 行照报，并说清是「库里本来就没有」：一个刚 init 完的库导出成功、
    # 文件里只有表头，是完全正常的结果，不说清楚用户会以为导出失败了。
    line = f"已导出 {len(dataset.rows)} 行到 {out_path}"
    if not dataset.rows:
        line += f"（{dataset.empty_hint}）"
    click.echo(line)
