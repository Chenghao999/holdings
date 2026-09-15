"""holdings import 命令：CSV 批量导入。"""

from __future__ import annotations

import csv
from datetime import date

import click

from holdings.models.enums import MarketType, TradeType
from holdings.models.transaction import Transaction


@click.command()
@click.option(
    "--file", "file_path", required=True, type=click.Path(exists=True), help="CSV 文件路径"
)
@click.option("--group", default=None, help="组合分组")
@click.option("--fee-column", default=None, help="费用列名，映射到 fee 字段")
def import_cmd(file_path: str, group: str | None, fee_column: str | None) -> None:
    """从 CSV 批量导入历史交易。"""
    from holdings.storage import transaction_dao
    from holdings.utils.config import load_config

    cfg = load_config()
    count = 0
    with open(file_path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            fee = float(row[fee_column]) if (fee_column and row.get(fee_column)) else 0.0
            tx = Transaction(
                symbol=row["symbol"],
                market=MarketType(row.get("market", "A股")),
                asset_type=_infer(row.get("asset_type", "stock")),
                trade_date=date.fromisoformat(row["trade_date"]),
                trade_type=TradeType(row["trade_type"]),
                quantity=float(row["quantity"]),
                price=float(row["price"]),
                fee=fee,
                portfolio_group=group or cfg.default_group,
                notes=row.get("notes"),
            )
            transaction_dao.add(cfg.database_path, tx)
            count += 1
    click.echo(f"已导入 {count} 笔交易")


def _infer(asset_type: str):
    from holdings.models.enums import AssetType

    return AssetType(asset_type)
