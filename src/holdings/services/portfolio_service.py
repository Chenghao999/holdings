"""持仓汇总服务：编排 storage + portfolio，返回纯数据对象。"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from holdings.models.enums import MarketType
from holdings.portfolio import allocator, calculator
from holdings.storage import asset_meta_dao, price_cache_dao, transaction_dao
from holdings.utils.formatter import (
    currency_label,
    format_money,
    format_percent,
    format_price,
    format_quantity,
)

#: 基准货币。汇总只按人民币相加——持有美股 + A 股时把美元和人民币当成同一种
#: 货币加起来，得到的数看着完全正常，却是错的。汇率换算留到 v2.0.0，本轮做的
#: 是「不混加、如实说明」：非基准货币的标的不进汇总，由提示行报出来。
#: 与 `AssetMeta.currency` / `price_cache.currency` 的默认值一致。
BASE_CURRENCY = "CNY"

#: 持仓表的列与显示名，顺序即显示顺序。
#:
#: 放在这里而不是某个界面里：它是「服务产出什么」与「界面怎么显示」之间的契约。
#: CLI 的表格、`--sort` 的取值、TUI 的表头都从这一份派生——各家自己写一份的话，
#: 服务改了列名只会让其中一家悄悄出错。文字标签放在服务层确实不算常见，
#: 但**同一张表在两个界面里叫法不一致**是更实际的问题。
HOLDINGS_COLUMNS = {
    "symbol": "代码",
    "name": "名称",
    "market": "市场",
    "asset_type": "类型",
    "quantity": "数量",
    "avg_cost": "成本价",
    "current_price": "现价",
    "market_value": "市值",
    "total_fees": "累计费用",
    "profit": "盈亏",
    "profit_rate": "盈亏率",
}


def holdings_cell(column: str, row) -> str:
    """把持仓表里的一格格式化成显示文本。`row` 是 DataFrame 的一行。

    与 `HOLDINGS_COLUMNS` 放在同一处、理由也相同：列名只是契约的一半，
    「这一列按金额还是按单价显示」是另一半。TUI 与 Web 各写一份的话，
    服务层改了列的含义，两边会以不同的速度走样——而它们显示的是同一张表。
    文字标签放在服务层确实不算常见，但**同一格数字在两个界面里印得不一样**
    是更实际的故障。

    算不出来的值在 df 里是 `NaN`，各 `format_*` 一律显示成 `—`，
    这里不再判断一次——口径归 `utils/formatter.py` 一处管。
    """
    if column == "quantity":
        return format_quantity(row.get(column))
    if column == "avg_cost":
        return format_price(row.get(column))
    if column == "current_price":
        return _price_cell(row)
    if column in {"market_value", "total_fees", "profit"}:
        return format_money(row.get(column))
    if column == "profit_rate":
        return format_percent(row.get(column))
    return str(row.get(column, ""))


def _price_cell(row) -> str:
    """现价，外币的带上币种。

    同一列里混着两种货币而不加标注，等于把「不混加」这件事做了一半：
    用户看到的仍是一个没有单位的数。非基准货币才标——每行都挂一个 `CNY`
    只会把这一列撑宽，而人民币是本工具的默认口径。
    """
    price = format_price(row.get("current_price"))
    currency = row.get("currency")
    # `isinstance` 而不是判空：DataFrame 里的缺失值可能是 `None`，也可能是 NaN。
    if not isinstance(currency, str) or currency == BASE_CURRENCY:
        return price
    return f"{price} {currency}"


@dataclass
class PortfolioSummary:
    """持仓汇总结果，纯数据，供 CLI / GUI 渲染。

    **汇总的口径是「能按基准货币计价的标的」**，即同时满足两个条件：有行情，
    且行情是按 `BASE_CURRENCY` 报的。剩下的两类都进不了汇总——没有行情的标的
    市值算不出来，让它以 0 参与汇总就是 `list` 里那个「血亏 100%」的来源；
    外币计价的标的市值是真的，但它和人民币的成本加不到一起。两类各自由
    `unpriced_symbols` / `foreign_holdings` 如实报出来，渲染层据此提示用户。

    `total_value` / `total_cost` 在**一个标的都计不进来**时是 `None`，不是 0：
    「总市值 0」看着像空仓，而事实是持有着、只是没法按人民币说清楚。
    """

    total_value: float | None
    total_cost: float | None
    total_profit: float | None
    profit_rate: float | None
    total_fees: float
    allocation: dict
    holdings_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    fee_breakdown: dict = field(default_factory=dict)
    #: 没有行情的标的（按代码）。非空时汇总行里的市值与盈亏都只覆盖其余标的。
    unpriced_symbols: list[str] = field(default_factory=list)
    #: 这些标的的成本合计，供提示行说明「没算进去的是多少」。
    unpriced_cost: float = 0.0
    #: 非基准货币计价的标的：代码 → 币种。它们的市值与人民币不可比，
    #: 因此不进汇总，行内也不显示市值与盈亏。
    foreign_holdings: dict[str, str] = field(default_factory=dict)
    #: 这些标的的成本合计（按用户录入时的货币计，未换算）。
    foreign_cost: float = 0.0


def get_summary(db_path: str, group: str | None = None) -> PortfolioSummary:
    """计算持仓汇总，不输出任何文字。"""
    transactions = transaction_dao.get_all(db_path, group=group)
    positions = calculator.compute_positions(transactions)

    # 资产类型映射（用于配置占比）
    asset_types = {t.symbol: t.asset_type.value for t in transactions}

    # 含费用汇总（成本是账本事实，与有没有行情无关）。这一项**不按币种拆分**：
    # 交易流水里没有币种字段，无从判断一笔费用记的是哪种货币，拿行情缓存的币种
    # 去反推账本的口径只是另一层猜测。
    total_fees = calculator.summarize(positions)["total_fees"]

    # 标的名称。一次取全表而不是逐条 get（N+1），取不到就回落到代码——
    # 名称是用来认人的，没有名字时代码本身就是最好的名字。
    names = {m.symbol: (m.name or m.symbol) for m in asset_meta_dao.get_all(db_path)}

    holdings_rows = []
    market_values: dict[str, float] = {}
    unpriced_symbols: list[str] = []
    foreign_holdings: dict[str, str] = {}
    priced_cost = 0.0
    unpriced_cost = 0.0
    foreign_cost = 0.0
    for symbol, pos in positions.items():
        if pos.quantity <= 0:
            continue
        cached = price_cache_dao.get(db_path, symbol)
        currency = cached.currency if cached else None
        # 进得了汇总的前提是有行情、且行情按基准货币报。汇率换算留到 v2.0.0，
        # 这里只保证不给一个把两种货币加起来的数。
        countable = cached is not None and currency == BASE_CURRENCY
        # 传给 holding_for 的是「算不算得出来」：算不出来时它给 None（而不是 0），
        # 市值 / 盈亏 / 盈亏率一并变成「不知道」，渲染层显示 `—`。
        h = calculator.holding_for(pos, cached.price if countable else None)
        holdings_rows.append(
            {
                "symbol": h.symbol,
                "name": names.get(symbol, symbol),
                "market": _market_of(transactions, symbol),
                "asset_type": asset_types.get(symbol, "stock"),
                "quantity": h.quantity,
                "avg_cost": round(h.avg_cost, 4),
                # 现价与币种照实带上：价格取到了就是取到了，有没有进汇总
                # 是另一回事。外币的现价由渲染层标注币种，否则同一列里
                # 混着两种货币而不说明，等于没排除混加。
                "current_price": cached.price if cached else None,
                "currency": currency,
                "market_value": h.market_value,
                "total_fees": round(h.total_fees, 4),
                "profit": h.profit,
                "profit_rate": h.profit_rate,
            }
        )
        if cached is None:
            unpriced_symbols.append(symbol)
            unpriced_cost += pos.total_cost
        elif not countable:
            foreign_holdings[symbol] = currency
            foreign_cost += pos.total_cost
        else:
            priced_cost += pos.total_cost
            market_values[symbol] = h.market_value

    holdings_df = pd.DataFrame(holdings_rows)

    excluded = bool(unpriced_symbols or foreign_holdings)
    if excluded and not market_values:
        # 一个标的都计不进来：总额不是 0，是未知。印 0.00 只会是第二个
        # 「看着像结论」的假数字。
        total_value: float | None = None
        total_cost: float | None = None
        total_profit: float | None = None
        profit_rate: float | None = None
    else:
        total_value = sum(market_values.values())
        total_cost = priced_cost
        # pandas 的 sum 跳过 NaN，正好等于「计得进来的那些标的的盈亏合计」：
        # 没行情与外币计价的标的在 df 里就是 NaN。
        total_profit = float(holdings_df["profit"].sum()) if not holdings_df.empty else 0.0
        # 分母只算计得进来的成本：分子里的盈亏同样只含有行情的标的，
        # 两边口径不一致会算出一个既不是「全体」也不是「部分」的数。
        profit_rate = (total_profit / priced_cost * 100) if priced_cost else 0.0

    alloc = allocator.allocation_by_asset_type(market_values, asset_types)

    return PortfolioSummary(
        total_value=total_value,
        total_cost=total_cost,
        total_profit=total_profit,
        profit_rate=profit_rate,
        total_fees=total_fees,
        allocation=alloc,
        holdings_df=holdings_df,
        fee_breakdown=calculator.fee_breakdown(transactions),
        unpriced_symbols=unpriced_symbols,
        unpriced_cost=unpriced_cost,
        foreign_holdings=foreign_holdings,
        foreign_cost=foreign_cost,
    )


def unpriced_hint(summary: PortfolioSummary) -> str | None:
    """没有行情的标的提示。没有返回 None，调用方据此决定印不印。

    这两条提示（还有 `foreign_hint`）放在服务层，而不是某个界面里：它们是
    **口径的一部分**——「上面的总额里少算了什么」必须和那个总额一起读。
    三个界面各写一遍的话，改口径时最容易漏掉其中一句，用户就会把一个自己
    不知道是部分的数当成全部。界面只负责给它上色（CLI 裹 `[yellow]`、
    Web 裹一个 class）。
    """
    if not summary.unpriced_symbols:
        return None
    return (
        f"{len(summary.unpriced_symbols)} 个标的无行情"
        f"（成本合计 {format_money(summary.unpriced_cost)}），未计入上面的汇总；"
        f"请先执行 holdings sync"
    )


def foreign_hint(summary: PortfolioSummary) -> str | None:
    """非基准货币计价的标的提示。没有返回 None。

    措辞要说明的是「没加进去」而不是「加不了」：本工具不做汇率换算，用户要知道
    上面的总额里少算了什么，才不会把总和当成全部身家。
    """
    if not summary.foreign_holdings:
        return None
    # 先按币种代码排序再换成显示名：按显示名排的结果依赖中文的码位，看着像顺序，
    # 其实是巧合。
    codes = sorted(set(summary.foreign_holdings.values()))
    currencies = "、".join(currency_label(code) for code in codes)
    return (
        f"{len(summary.foreign_holdings)} 个标的以{currencies}计价"
        f"（成本合计 {format_money(summary.foreign_cost)}），未计入上面的汇总；"
        f"本工具按人民币口径汇总，不做汇率换算"
    )


def _market_of(transactions, symbol: str) -> str:
    for t in transactions:
        if t.symbol == symbol:
            return t.market.value
    return MarketType.A_SHARE.value
