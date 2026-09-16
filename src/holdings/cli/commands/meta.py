"""holdings meta 命令：维护标的的基础信息（名称、币种、年化管理费率）。

单独成一条命令而不是往 `add` 上加 `--name`：那些参数与「记一笔交易」无关，
塞进去只会让 `add` 的参数表更长。
"""

from __future__ import annotations

import click

from holdings.models.asset_meta import AssetMeta


@click.command()
@click.option("--symbol", required=True, help="标的代码")
@click.option("--name", default=None, help="名称，如「黄金ETF」")
@click.option("--currency", default=None, help="币种，默认 CNY")
@click.option(
    "--fee-rate",
    type=float,
    default=None,
    help="年化管理费率（%），仅作参考展示，不参与成本计算",
)
@click.option("--remove", is_flag=True, help="删除该标的的基础信息")
def meta_cmd(
    symbol: str,
    name: str | None,
    currency: str | None,
    fee_rate: float | None,
    remove: bool,
) -> None:
    """维护标的的基础信息（`holdings list` 的名称列取自这里）。"""
    from holdings.services import asset_meta_service
    from holdings.utils.config import load_config

    cfg = load_config()

    if remove:
        if asset_meta_service.remove(cfg.database_path, symbol):
            click.echo(f"已删除 {symbol} 的基础信息")
        else:
            click.echo(f"{symbol} 没有基础信息可删")
        return

    if name is None and currency is None and fee_rate is None:
        # 一个字段都没给：把这当作「查一下现在记的是什么」，而不是写一条空记录。
        # 顺手写成空记录会静默清掉已有的名称与费率。
        existing = asset_meta_service.get(cfg.database_path, symbol)
        if existing is None:
            click.echo(f"{symbol} 还没有基础信息")
        else:
            click.echo(_describe(existing))
        return

    existing = asset_meta_service.get(cfg.database_path, symbol)
    meta = AssetMeta(
        symbol=symbol,
        name=name if name is not None else (existing.name if existing else None),
        currency=currency if currency is not None else (existing.currency if existing else "CNY"),
        annual_management_fee=(
            fee_rate
            if fee_rate is not None
            else (existing.annual_management_fee if existing else 0.0)
        ),
    )
    asset_meta_service.record(cfg.database_path, meta)
    click.echo(f"已记录：{_describe(meta)}")
    if fee_rate is not None:
        click.echo("年化管理费率仅作参考展示，不参与成本计算；真实费用请用 add --fee 逐笔记录")


def _describe(meta: AssetMeta) -> str:
    parts = [meta.symbol]
    if meta.name:
        parts.append(meta.name)
    parts.append(f"币种 {meta.currency}")
    if meta.annual_management_fee:
        parts.append(f"年化管理费率 {meta.annual_management_fee:g}%")
    return " | ".join(parts)
