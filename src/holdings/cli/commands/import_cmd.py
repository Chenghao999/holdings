"""holdings import 命令：对账单批量导入。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date

import click

from holdings.exceptions import TradeValidationError
from holdings.models.asset_meta import AssetMeta
from holdings.models.enums import (
    AssetType,
    MarketType,
    NonTradeType,
    TradeType,
    classify_trade_type,
)
from holdings.models.statement import StatementRow
from holdings.models.transaction import Transaction
from holdings.services.trade_service import Duplicate

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


@dataclass(frozen=True)
class PostedRow:
    """一行会入账的记录，带着它在文件里的行号。

    行号得一直带到落库前：查重报出来的是「第几行重复」，而 `Transaction`
    对应的是账本、没有行号可言。
    """

    line_no: int
    transaction: Transaction
    #: 文件里这一列是空的——落库前会按代码去数据源补，补不到才沿用默认值
    #: （见 `_complete_instruments`）。文件写了的以文件为准，不去问。
    needs_market: bool = False
    needs_asset_type: bool = False


@dataclass(frozen=True)
class Defaulted:
    """文件里空着、数据源也没问到，最终按默认值记下的一列。

    记到**列**而不是行：市场查到了而资产类型没查到是常事（不是每个源都分得出
    股票与 ETF），说成「这一行没取到」就成了假话，用户会以为市场也是默认值。
    """

    line_no: int
    column: str
    value: str


@click.command()
@click.option(
    "--file", "file_path", required=True, type=click.Path(exists=True), help="对账单文件路径"
)
@click.option(
    "--group", default=None, help="组合分组；对账单带资金账号时以账号为准，它只接住没有账号的行"
)
@click.option("--broker", default=None, help="对账单格式名；不给则按表头自动识别")
@click.option("--fee-column", default=None, help="费用列名（照文件里的写法），覆盖格式自带的费用列")
@click.option("--strict", is_flag=True, help="有未入账的行时一笔都不写，并以退出码 5 结束")
@click.option(
    "--dedupe",
    type=click.Choice(["error", "skip", "off"]),
    default="error",
    show_default=True,
    help="重复行怎么办：error 报错、一笔不写；skip 跳过重复的；off 不查重",
)
def import_cmd(
    file_path: str,
    group: str | None,
    broker: str | None,
    fee_column: str | None,
    strict: bool,
    dedupe: str,
) -> None:
    """从对账单文件批量导入历史交易。

    整批校验、整批落库：任何一行非法都不会写入任何数据，并指出出错的行号。

    对账单里认得出、但本工具不入账的行（分红、送转、配股、银证转账、利息）
    同样一笔不写，但会逐行列出行号与原因——静默跳过会让「导入成功」变成假话。

    同一份文件导两遍、或逐月导出时月份之间有重叠，重复的行**默认报错而不是
    跳过**：静默跳过与静默重复一样坏，一个少算一个多算，用户都看不出来。
    确认不是同一笔（同一天同价同费的两笔真实成交）再用 `--dedupe off` 放行。

    对账单里有资金账号时，**按账号分别落成组合分组**：文件说得比命令行细，
    这时 `--group` 只接住没有账号的行（BACKLOG B-32）。
    """
    from holdings.services import asset_meta_service, import_service, trade_service
    from holdings.utils.config import load_config

    cfg = load_config()
    statement = import_service.read_statement(file_path, broker=broker, fee_column=fee_column)
    if not statement.rows:
        click.echo("文件中没有数据行，未导入任何交易")
        return

    # 自动识别挑中了谁要说出来：认错了才有得查，而识别本身不报错。
    click.echo(f"解析格式：{statement.broker_label}")

    posted, unposted = _split_rows(
        statement.rows, group or cfg.default_group, statement.broker_name
    )

    # --strict 是「要么全进、要么不进」，而不是「先进去再报错」：本命令的契约
    # 本来就是整批校验、整批写入——写了一半又以非零退出码结束，用户重跑一次
    # 就把账翻倍了（这也正是 import 必须幂等的原因，BACKLOG B-29）。
    if strict and unposted:
        _echo_unposted(unposted)
        raise TradeValidationError(
            f"{len(unposted)} 行未入账（第 {_line_numbers(unposted)} 行），"
            "已按 --strict 中止，未写入任何数据"
        )

    # 查重默认只是**报出来**：判重靠指纹（标的 + 日期 + 类型 + 数量 + 价格 + 费用），
    # 而同一天同价同费分两笔买入是真实存在的成交，指纹分不开。所以丢不丢由用户定，
    # 工具不替他决定——静默跳过与静默重复一样坏。
    duplicates: list[Duplicate] = []
    if dedupe != "off":
        duplicates = trade_service.find_duplicates(
            cfg.database_path, [row.transaction for row in posted]
        )
        if duplicates:
            _echo_duplicates(posted, duplicates)
            if dedupe == "error":
                raise TradeValidationError(
                    f"{len(duplicates)} 行与已有记录重复（第 "
                    f"{'、'.join(str(posted[d.index].line_no) for d in duplicates)} 行），"
                    "未写入任何数据；确认不是同一笔就加 --dedupe off，"
                    "要跳过重复行就加 --dedupe skip"
                )
            dropped = {duplicate.index for duplicate in duplicates}
            posted = [row for index, row in enumerate(posted) if index not in dropped]

    # 补全放在校验与查重**之后**：上面两步都可能整批中止，而这一步会联网、
    # 还会把查到的资料写进 `asset_meta` 缓存——一次失败的导入不该留下痕迹。
    posted, defaulted = _complete_instruments(posted, cfg.database_path, asset_meta_service.lookup)

    # 整批校验通过才落库；TradeValidationError 冒泡到入口，映射为退出码 5。
    ids = trade_service.add_transactions(cfg.database_path, [row.transaction for row in posted])
    _echo_summary(
        len(statement.rows),
        len(ids),
        unposted,
        None if dedupe == "off" else len(duplicates),
        _group_counts(posted),
        defaulted,
    )


def _split_rows(
    rows: list[StatementRow], fallback_group: str, source: str
) -> tuple[list[PostedRow], list[UnpostedRow]]:
    """把对账单的行分成「入账的交易」与「认得出但不入账的行」。

    `trade_type` **认不出**的行仍然整批拒绝（退出码 5），与改动前一致：
    「这个值非法」要用户去改文件，「这个值认识、只是暂不入账」只要用户知道。
    把后者也当成错误，一份正确的对账单就永远导不进来；把前者当成不入账放过，
    用户改错了文件却什么也看不到。

    **组合分组按对账单里的资金账号分，`--group` 只接住没有账号的行。**
    文件说得很清楚每一行属于哪个账号，命令行的参数说不了这么细；反过来让
    `--group` 压过账号，一份两账号的对账单就被并成一个组，而用户在汇总里
    看不出来——所以是账号优先，`--group` 只当兜底（BACKLOG B-32）。
    """
    posted: list[PostedRow] = []
    unposted: list[UnpostedRow] = []
    for row in rows:
        raw_type = row.get("trade_type")
        category = classify_trade_type(raw_type)
        if isinstance(category, NonTradeType):
            unposted.append(UnpostedRow(row.line_no, raw_type, category))
        elif category is None:
            raise TradeValidationError(
                f"第 {row.line_no} 行 trade_type 列不是合法交易类型：{raw_type}"
            )
        else:
            group = row.get("account") or fallback_group
            posted.append(
                PostedRow(
                    line_no=row.line_no,
                    transaction=_row_to_transaction(row, group, category, source),
                    needs_market=not row.get("market"),
                    needs_asset_type=not row.get("asset_type"),
                )
            )
    return posted, unposted


def _complete_instruments(
    posted: list[PostedRow],
    db_path: str,
    lookup: Callable[..., AssetMeta | None],
) -> tuple[list[PostedRow], list[Defaulted]]:
    """按代码把市场与资产类型补上，返回补好的行与**按默认值记的那几列**。

    券商 CSV 里通常只有代码，此前 `market` 缺省成 A 股、`asset_type` 缺省成
    stock，于是一份美股对账单整份被记成 A 股——`report` / `sync` 据此取价，
    取不到只显示 `—`，用户得逐个用 `meta` 手工修（BACKLOG B-32）。

    文件里写了的以文件为准（它比按代码形状排的顺序准），只补空的那些列；
    两列都写了也仍去查一次，那是为了把**名称**落进 `asset_meta`，
    `holdings list` 的名称列才显示得出来。

    **补不到不是错误**：一份对账单不该因为没网就导不进来，缺的列沿用默认值，
    但用了哪些默认值要报出来——不说明就等于把默认值当成了事实。

    `lookup` 按 (代码, 市场) 记忆：对账单里同一个标的会出现很多行，
    逐行去问是白问。传的是 `asset_meta_service.lookup`，好让用例能换掉它。
    """
    asked: dict[tuple[str, MarketType | None], AssetMeta | None] = {}
    completed: list[PostedRow] = []
    defaulted: list[Defaulted] = []
    for row in posted:
        transaction = row.transaction
        # 市场是默认值时不拿它去查——那正是要查掉的东西。
        market = None if row.needs_market else transaction.market
        key = (transaction.symbol, market)
        if key not in asked:
            asked[key] = lookup(db_path, transaction.symbol, market)
        meta = asked[key]

        market_from_source = _market_of(meta) if row.needs_market and meta is not None else None
        asset_type_from_source = (
            meta.asset_type if row.needs_asset_type and meta is not None else None
        )

        # 报的是**这一列**没问到，不是「整行没取到」：市场查到了而资产类型没查到
        # 是常事（不是每个源都分得出股票与 ETF），说成整行没取到就成了假话。
        if row.needs_market and market_from_source is None:
            defaulted.append(Defaulted(row.line_no, "市场", transaction.market.value))
        if row.needs_asset_type and asset_type_from_source is None:
            defaulted.append(Defaulted(row.line_no, "资产类型", transaction.asset_type.value))

        if market_from_source is None and asset_type_from_source is None:
            completed.append(row)
            continue
        completed.append(
            replace(
                row,
                # `Transaction` 是 pydantic 模型不是 dataclass，改字段要用
                # `model_copy(update=...)`。这里不传 `model_validate`：赋进去的
                # 是枚举成员本身，不是需要解析的原始值。
                transaction=transaction.model_copy(
                    update={
                        "market": market_from_source or transaction.market,
                        "asset_type": asset_type_from_source or transaction.asset_type,
                    }
                ),
            )
        )
    return completed, defaulted


def _market_of(meta: AssetMeta) -> MarketType | None:
    """`AssetMeta.market` 是字符串（那是数据库里的样子），转不回枚举就当没查到。

    转不回来要么是用户在 `holdings meta` 里手填了个不存在的市场，要么是更早的
    版本写坏了库。这两种都不该让**整份对账单导不进来**，也不该拿一个瞎猜的
    市场顶上——当作没查到，让它落到默认值，汇总里那一行会被报出来。

    空值与 `None` 不必单独判：`MarketType("")` 同样抛 `ValueError`。
    """
    try:
        return MarketType(meta.market)
    except ValueError:
        return None


def _group_counts(posted: list[PostedRow]) -> dict[str, int]:
    """落进每个组合各多少笔。

    从**最终要写的那批**上数，而不是拆分时数：`--dedupe skip` 会丢掉几行，
    按拆分时的数报出来就与「入账 N 笔」对不上了。
    """
    counts: dict[str, int] = {}
    for row in posted:
        group = row.transaction.portfolio_group
        counts[group] = counts.get(group, 0) + 1
    return counts


def _echo_summary(
    total: int,
    posted: int,
    unposted: list[UnpostedRow],
    duplicates: int | None,
    groups: dict[str, int],
    defaulted: list[Defaulted],
) -> None:
    """固定三段：识别 / 入账 / 未入账。

    未入账是 0 也照印——「0」是被数出来的，不是没数，用户才能相信它。
    重复那一截同理，只在**真的查过**时才印：`--dedupe off` 印「重复 0 行」
    就成了谎话，那是没查，不是没重复。

    **落组那一截只在真有多个组时印**：一个组是常态，每次都印就成了废话；
    而一旦对账单里的账号让账分散到几个组，用户必须当场知道——否则他按
    `holdings list` 的默认分组去看，会以为这笔导入丢了。

    **标的资料那一截必须逐列报出没取到的**：默认值本身没有错，但把默认值
    当成事实才是错的——一份被整份记成 A 股的美股对账单，用户不去查就永远
    不知道（BACKLOG B-32）。
    """
    line = f"识别 {total} 行，入账 {posted} 笔，未入账 {len(unposted)} 行"
    if duplicates is not None:
        line += f"，重复 {duplicates} 行"
    click.echo(line)
    if len(groups) > 1:
        breakdown = "、".join(f"{name} {count} 笔" for name, count in groups.items())
        click.echo(f"落组：{breakdown}")
    _echo_instruments(posted, defaulted)
    _echo_unposted(unposted)


def _echo_instruments(posted: int, defaulted: list[Defaulted]) -> None:
    """标的资料是取到的还是按默认值记的。

    **一行都没有时不印这一截**：一份整批未入账的对账单本来就没标的资料可言，
    印一句「全部取自对账单或数据源」是在拿 0 当成绩。

    取不到不是错误（离线照常导入），但**必须逐列说出来**：不说，用户就以为
    市场是从对账单里读出来的，而实际是默认值。
    """
    if not posted:
        return
    if not defaulted:
        click.echo("标的资料：全部取自对账单或数据源")
        return
    rows = len({item.line_no for item in defaulted})
    click.echo(f"标的资料：{rows} 行有列按默认值记")
    for item in defaulted:
        click.echo(f"  第 {item.line_no} 行{item.column}没取到，按默认值记：{item.value}")
    click.echo("  对不上的可用 holdings meta 改")


def _echo_duplicates(posted: list[PostedRow], duplicates: list[Duplicate]) -> None:
    """逐行报出重复的，并说清是与谁重复。

    带上这笔的金额与日期：用户要凭这一行判断「确实是同一笔」还是「两笔真实
    成交被指纹看成了一笔」，光给行号他判断不了。
    """
    for duplicate in duplicates:
        row = posted[duplicate.index]
        if duplicate.existing_id is not None:
            where = f"与库里已有的 #{duplicate.existing_id} 是同一笔"
        else:
            where = f"与第 {posted[duplicate.earlier].line_no} 行是同一笔"
        click.echo(f"  第 {row.line_no} 行重复：{where}——{_describe(row.transaction)}")


def _describe(tx: Transaction) -> str:
    return (
        f"{tx.symbol} {tx.trade_date.isoformat()} {tx.trade_type.value} "
        f"{tx.quantity:g} @ {tx.price:g}"
    )


def _echo_unposted(unposted: list[UnpostedRow]) -> None:
    for row in unposted:
        # 只在叫法与类别名不同时补一句，免得印成「分红派息（分红派息）」。
        label = row.raw_type
        if label != row.category.value:
            label = f"{label}（{row.category.value}）"
        click.echo(f"  第 {row.line_no} 行 {label}，未入账：{UNPOSTED_REASONS[row.category]}")


def _line_numbers(unposted: list[UnpostedRow]) -> str:
    return "、".join(str(row.line_no) for row in unposted)


def _row_to_transaction(
    row: StatementRow, group: str, trade_type: TradeType, source: str
) -> Transaction:
    """把一行对账单转成 Transaction，出错时带上行号与列名。

    `trade_type` 由调用方判定后传入：入账与否在 `_split_rows` 已经分过，
    这里再解一次，就会有第二个「什么算合法交易类型」的答案。
    """
    line_no = row.line_no

    def fail(column: str, reason: str) -> TradeValidationError:
        return TradeValidationError(f"第 {line_no} 行 {column} 列{reason}")

    raw_date = row.get("trade_date")
    try:
        trade_date = date.fromisoformat(raw_date)
    except ValueError:
        raise fail("trade_date", f"不是合法日期（应为 YYYY-MM-DD）：{raw_date}") from None

    raw_market = row.get("market")
    try:
        market = MarketType(raw_market or MarketType.A_SHARE.value)
    except ValueError:
        raise fail("market", f"不是合法市场：{raw_market}") from None

    raw_asset_type = row.get("asset_type")
    try:
        asset_type = AssetType(raw_asset_type or AssetType.STOCK.value)
    except ValueError:
        raise fail("asset_type", f"不是合法资产类型：{raw_asset_type}") from None

    raw_quantity = row.get("quantity")
    try:
        quantity = float(raw_quantity)
    except ValueError:
        raise fail("quantity", f"不是合法数字：{raw_quantity}") from None

    raw_price = row.get("price")
    try:
        price = float(raw_price)
    except ValueError:
        raise fail("price", f"不是合法数字：{raw_price}") from None

    # 费用列叫什么由解析器说了算（`佣金` / `手续费` / 三列相加），
    # 报错得用它的叫法，否则用户在自己的文件里找不到「fee」这一列。
    raw_fee = row.get("fee")
    try:
        fee = float(raw_fee) if raw_fee else 0.0
    except ValueError:
        raise fail(row.fee_source, f"不是合法数字：{raw_fee}") from None

    return Transaction(
        symbol=row.get("symbol"),
        market=market,
        asset_type=asset_type,
        trade_date=trade_date,
        trade_type=trade_type,
        quantity=quantity,
        price=price,
        fee=fee,
        portfolio_group=group,
        # 没有备注列时存 NULL 而不是空串：「没写备注」与「写了个空备注」
        # 在查询与展示上是两回事（同 SCHEMA 里 snapshot.note 的口径）。
        notes=row.get("notes") or None,
        source=source,
        # 流水号是可选的：有它的对账单判重能精确到笔，没有就退到指纹。
        external_id=row.get("external_id") or None,
    )
