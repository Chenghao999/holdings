"""holdings import 命令：CSV 批量导入。"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date

import click

from holdings.exceptions import TradeValidationError
from holdings.models.enums import (
    AssetType,
    MarketType,
    NonTradeType,
    TradeType,
    classify_trade_type,
)
from holdings.models.transaction import Transaction

REQUIRED_COLUMNS = ("symbol", "trade_date", "trade_type", "quantity", "price")

#: 每一类不入账的行为什么不入账。措辞要让用户明白「没坏，只是没做」——
#: 含糊其辞会被读成「已经处理过了」。
UNPOSTED_REASONS: dict[NonTradeType, str] = {
    NonTradeType.DIVIDEND: "分红如何摊销成本尚未支持（见 BACKLOG B-23）",
    NonTradeType.BONUS_SHARE: "送股/转增同时改变数量与成本价，口径尚未支持（见 BACKLOG B-23）",
    NonTradeType.RIGHTS_ISSUE: "配股缴款的口径尚未支持（见 BACKLOG B-23）",
    NonTradeType.TRANSFER: "银证转账动的是现金，不影响持仓",
    NonTradeType.INTEREST: "利息不计入持仓成本",
}


@dataclass(frozen=True)
class UnpostedRow:
    """一行认得出来、但本工具不入账的记录。"""

    line_no: int
    raw_type: str
    category: NonTradeType


@click.command()
@click.option(
    "--file", "file_path", required=True, type=click.Path(exists=True), help="CSV 文件路径"
)
@click.option("--group", default=None, help="组合分组")
@click.option("--fee-column", default=None, help="费用列名，映射到 fee 字段")
@click.option("--strict", is_flag=True, help="有未入账的行时一笔都不写，并以退出码 5 结束")
def import_cmd(file_path: str, group: str | None, fee_column: str | None, strict: bool) -> None:
    """从 CSV 批量导入历史交易。

    整批校验、整批落库：任何一行非法都不会写入任何数据，并指出出错的行号。

    对账单里认得出、但本工具不入账的行（分红、送转、配股、银证转账、利息）
    同样一笔不写，但会逐行列出行号与原因——静默跳过会让「导入成功」变成假话。
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

    transactions, unposted = _split_rows(rows, group or cfg.default_group, fee_column)

    # --strict 是「要么全进、要么不进」，而不是「先进去再报错」：本命令的契约
    # 本来就是整批校验、整批写入，而 import 目前还没有幂等（BACKLOG B-29）——
    # 写了一半又以非零退出码结束，用户重跑一次就把账翻倍了。
    if strict and unposted:
        _echo_unposted(unposted)
        raise TradeValidationError(
            f"{len(unposted)} 行未入账（第 {_line_numbers(unposted)} 行），"
            "已按 --strict 中止，未写入任何数据"
        )

    # 整批校验通过才落库；TradeValidationError 冒泡到入口，映射为退出码 5。
    ids = trade_service.add_transactions(cfg.database_path, transactions)
    _echo_summary(len(rows), len(ids), unposted)


def _split_rows(
    rows: list[dict[str, str]], group: str, fee_column: str | None
) -> tuple[list[Transaction], list[UnpostedRow]]:
    """把 CSV 行分成「入账的交易」与「认得出但不入账的行」。

    `trade_type` **认不出**的行仍然整批拒绝（退出码 5），与改动前一致：
    「这个值非法」要用户去改文件，「这个值认识、只是暂不入账」只要用户知道。
    把后者也当成错误，一份正确的对账单就永远导不进来；把前者当成不入账放过，
    用户改错了文件却什么也看不到。
    """
    transactions: list[Transaction] = []
    unposted: list[UnpostedRow] = []
    for line_no, row in enumerate(rows, start=2):  # 第 1 行是表头
        raw_type = (row.get("trade_type") or "").strip()
        category = classify_trade_type(raw_type)
        if isinstance(category, NonTradeType):
            unposted.append(UnpostedRow(line_no, raw_type, category))
        elif category is None:
            raise TradeValidationError(f"第 {line_no} 行 trade_type 列不是合法交易类型：{raw_type}")
        else:
            transactions.append(_row_to_transaction(row, line_no, group, fee_column, category))
    return transactions, unposted


def _echo_summary(total: int, posted: int, unposted: list[UnpostedRow]) -> None:
    """固定三段：识别 / 入账 / 未入账。

    未入账是 0 也照印——「0」是被数出来的，不是没数，用户才能相信它。
    """
    click.echo(f"识别 {total} 行，入账 {posted} 笔，未入账 {len(unposted)} 行")
    _echo_unposted(unposted)


def _echo_unposted(unposted: list[UnpostedRow]) -> None:
    for row in unposted:
        # 只在叫法与类别名不同时补一句，免得印成「分红派息（分红派息）」。
        label = row.raw_type
        if label != row.category.value:
            label = f"{label}（{row.category.value}）"
        click.echo(f"  第 {row.line_no} 行 {label}，未入账：{UNPOSTED_REASONS[row.category]}")


def _line_numbers(unposted: list[UnpostedRow]) -> str:
    return "、".join(str(row.line_no) for row in unposted)


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
    row: dict[str, str],
    line_no: int,
    group: str,
    fee_column: str | None,
    trade_type: TradeType,
) -> Transaction:
    """把一行 CSV 转成 Transaction，出错时带上行号与列名。

    `trade_type` 由调用方判定后传入：入账与否在 `_split_rows` 已经分过，
    这里再解一次，就会有第二个「什么算合法交易类型」的答案。
    """

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
