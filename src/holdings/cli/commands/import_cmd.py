"""holdings import 命令：CSV 批量导入。"""

from __future__ import annotations

import csv
from datetime import date

import click

from holdings.exceptions import TradeValidationError
from holdings.models.enums import AssetType, MarketType, TradeType
from holdings.models.transaction import Transaction

REQUIRED_COLUMNS = ("symbol", "trade_date", "trade_type", "quantity", "price")


@click.command()
@click.option(
    "--file", "file_path", required=True, type=click.Path(exists=True), help="CSV 文件路径"
)
@click.option("--group", default=None, help="组合分组")
@click.option("--fee-column", default=None, help="费用列名，映射到 fee 字段")
def import_cmd(file_path: str, group: str | None, fee_column: str | None) -> None:
    """从 CSV 批量导入历史交易。

    整批校验、整批落库：任何一行非法都不会写入任何数据，并指出出错的行号。
    """
    from holdings.services import trade_service
    from holdings.utils.config import load_config

    cfg = load_config()
    with open(file_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        _check_header(reader.fieldnames or [], fee_column)
        rows = list(reader)

    if not rows:
        click.echo("CSV 中没有数据行，未导入任何交易")
        return

    transactions = [
        _row_to_transaction(row, line_no, group or cfg.default_group, fee_column)
        for line_no, row in enumerate(rows, start=2)  # 第 1 行是表头
    ]

    # 整批校验通过才落库；TradeValidationError 冒泡到入口，映射为退出码 5。
    ids = trade_service.add_transactions(cfg.database_path, transactions)
    click.echo(f"已导入 {len(ids)} 笔交易")


def _check_header(fieldnames: list[str], fee_column: str | None) -> None:
    """校验表头。缺失列与不存在的费用列都在这里一次性报清楚。

    用 TradeValidationError（退出码 5）而非 click.BadParameter：
    这些是文件内容问题、不是命令行参数问题，报错文案也就不该带
    「Invalid value for ...」这类 click 前缀。
    """
    missing = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
    if missing:
        raise TradeValidationError(
            f"CSV 缺少必需列：{'、'.join(missing)}（现有列：{'、'.join(fieldnames)}）"
        )
    if fee_column and fee_column not in fieldnames:
        # 此前是静默按 0 计费，用户会以为费用导进来了。
        raise TradeValidationError(
            f"--fee-column 指定的列不存在：{fee_column}（现有列：{'、'.join(fieldnames)}）"
        )


def _row_to_transaction(
    row: dict[str, str], line_no: int, group: str, fee_column: str | None
) -> Transaction:
    """把一行 CSV 转成 Transaction，出错时带上行号与列名。"""

    def fail(column: str, reason: str) -> TradeValidationError:
        return TradeValidationError(f"第 {line_no} 行 {column} 列{reason}")

    try:
        trade_date = date.fromisoformat(row["trade_date"])
    except ValueError:
        raise fail("trade_date", f"不是合法日期（应为 YYYY-MM-DD）：{row['trade_date']}") from None

    try:
        market = MarketType(row.get("market") or MarketType.A_SHARE.value)
    except ValueError:
        raise fail("market", f"不是合法市场：{row.get('market')}") from None

    try:
        trade_type = TradeType(row["trade_type"])
    except ValueError:
        raise fail("trade_type", f"不是合法交易类型：{row['trade_type']}") from None

    try:
        asset_type = AssetType(row.get("asset_type") or AssetType.STOCK.value)
    except ValueError:
        raise fail("asset_type", f"不是合法资产类型：{row.get('asset_type')}") from None

    try:
        quantity = float(row["quantity"])
    except ValueError:
        raise fail("quantity", f"不是合法数字：{row['quantity']}") from None

    try:
        price = float(row["price"])
    except ValueError:
        raise fail("price", f"不是合法数字：{row['price']}") from None

    try:
        fee = float(row[fee_column]) if fee_column and row.get(fee_column) else 0.0
    except ValueError:
        raise fail(str(fee_column), f"不是合法数字：{row.get(fee_column)}") from None

    return Transaction(
        symbol=row["symbol"],
        market=market,
        asset_type=asset_type,
        trade_date=trade_date,
        trade_type=trade_type,
        quantity=quantity,
        price=price,
        fee=fee,
        portfolio_group=group,
        notes=row.get("notes"),
    )
