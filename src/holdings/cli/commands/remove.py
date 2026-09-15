"""holdings remove 命令。"""

from __future__ import annotations

import click


@click.command()
@click.option("--id", "tx_id", type=int, required=True, help="交易记录 ID")
def remove_cmd(tx_id: int) -> None:
    """删除指定 ID 的交易记录（需二次确认）。"""
    from holdings.storage import transaction_dao
    from holdings.utils.config import load_config

    cfg = load_config()
    tx = transaction_dao.get(cfg.database_path, tx_id)
    if tx is None:
        click.echo(f"未找到交易 #{tx_id}", err=True)
        raise SystemExit(2)

    if click.confirm(f"确认删除交易 #{tx_id}（{tx.symbol} {tx.trade_type.value}）？"):
        transaction_dao.remove(cfg.database_path, tx_id)
        click.echo(f"已删除交易 #{tx_id}")
    else:
        click.echo("已取消")
