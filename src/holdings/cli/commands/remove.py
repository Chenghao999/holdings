"""holdings remove 命令。"""

from __future__ import annotations

import click


@click.command()
@click.option("--id", "tx_id", type=int, required=True, help="交易记录 ID")
def remove_cmd(tx_id: int) -> None:
    """删除指定 ID 的交易记录（需二次确认）。"""
    from holdings.exceptions import RecordNotFoundError
    from holdings.services import trade_service
    from holdings.utils.config import load_config

    cfg = load_config()
    tx = trade_service.get_transaction(cfg.database_path, tx_id)
    if tx is None:
        # 抛出去由 main() 统一成「错误（2）：…」。此前这里自己 echo + SystemExit(2)：
        # 退出码是对的，但文案绕过了统一前缀，脚本按前缀匹配时会漏掉这一条。
        raise RecordNotFoundError(f"未找到交易 #{tx_id}")

    if click.confirm(f"确认删除交易 #{tx_id}（{tx.symbol} {tx.trade_type.value}）？"):
        trade_service.remove_transaction(cfg.database_path, tx_id)
        click.echo(f"已删除交易 #{tx_id}")
    else:
        click.echo("已取消")
