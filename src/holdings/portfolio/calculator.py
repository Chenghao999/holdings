"""持仓成本与盈亏计算（纯函数）。

采用移动加权平均法：
- 买入：费用计入成本，`新成本 = (旧数量×旧成本 + 新数量×新价 + 新费用) / (旧数量 + 新数量)`。
- 卖出：数量减少，成本价保持不变。
- FEE：不改变数量与成本，仅累计费用。
- 分红：摊薄成本——总成本减少「持股数 × 每股派息」，股数不变。
- 送股 / 转增 / 拆股：总成本不变、股数增加，成本价随之被摊薄。

本模块不依赖 storage / data，只接收交易序列做计算。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from holdings.exceptions import TradeValidationError
from holdings.models.enums import TradeType
from holdings.models.transaction import Transaction


@dataclass
class Position:
    """单标的持仓计算结果。"""

    symbol: str
    quantity: float = 0.0
    avg_cost: float = 0.0
    total_cost: float = 0.0  # 含费用的总成本
    total_fees: float = 0.0  # 累计费用
    realized_pnl: float = 0.0  # 已实现盈亏（卖出部分）


@dataclass
class Holding:
    """某标的某时间的最终持仓状态，可直接用于渲染与报表。

    `current_price` 为 `None` 表示**这只标的没有行情**（还没同步过，或者数据源
    没取到）。此时市值、盈亏、盈亏率**一律是 `None`，不是 0**：按 0 算出来的
    盈亏率是 −100%，用户看到的是「血亏 100%」，而事实只是「不知道」。
    渲染层据此显示 `—`。
    """

    symbol: str
    quantity: float
    avg_cost: float
    total_fees: float
    current_price: float | None = None
    market_value: float | None = None
    profit: float | None = None
    profit_rate: float | None = None


def _weighted_buy(pos: Position, tx: Transaction) -> None:
    new_qty = pos.quantity + tx.quantity
    total = pos.quantity * pos.avg_cost + tx.quantity * tx.price + tx.fee
    pos.quantity = new_qty
    pos.avg_cost = total / new_qty if new_qty else 0.0
    pos.total_cost += tx.quantity * tx.price + tx.fee
    pos.total_fees += tx.fee


def _sell(pos: Position, tx: Transaction) -> None:
    # 卖出成本价不变，已实现盈亏 = (卖出价 - 成本价) × 数量 - 费用
    pos.realized_pnl += (tx.price - pos.avg_cost) * tx.quantity - tx.fee
    pos.total_fees += tx.fee
    pos.quantity -= tx.quantity
    # 按比例减少总成本，保持成本价一致
    pos.total_cost = pos.avg_cost * pos.quantity
    if pos.quantity == 0:
        pos.avg_cost = 0.0


def _apply_fee(pos: Position, tx: Transaction) -> None:
    # FEE 不改变数量与成本，仅累计费用
    pos.total_fees += tx.fee


def _apply_dividend(pos: Position, tx: Transaction) -> None:
    """现金分红：摊薄持仓成本——总成本减少「持股数 × 每股派息」，股数不变。

    金额落在 `quantity × price`（持股数 × 每股派息），**不能落在 `fee`**：
    `holding_for` 会把 `total_fees` 从盈亏里再减一次，分红进了那一列就会被
    反着减掉，还会混进报表的「累计费用」。

    摊薄而不是记成一笔独立收益，是为了让报表的「总盈亏」自然包含分红，
    与券商 APP 上看到的成本价一致。代价是 `avg_cost` 从此不再等于「你花的钱」，
    文档与报表里的口径句都写明了这一点。
    """
    pos.total_cost -= tx.quantity * tx.price
    pos.avg_cost = pos.total_cost / pos.quantity if pos.quantity else 0.0


def _apply_bonus_share(pos: Position, tx: Transaction) -> None:
    """送股 / 转增 / 拆股：总成本不变、股数增加，成本价随之被摊薄。

    `quantity` 是**新增的股数**，不是拆分后的总股数：十送十就把送来的那 100 股
    写成 `quantity=100`，一股拆成十股就把多出来的 900 股写成 `quantity=900`。
    两种写法都保持 `total_cost == avg_cost × quantity` 这条不变量。
    """
    pos.quantity += tx.quantity
    pos.avg_cost = pos.total_cost / pos.quantity if pos.quantity else 0.0


#: 每一种 TradeType 的行为。**缺一个成员就是 KeyError**，不是静默跳过——
#: 从前这里是三个没有 `else` 的 `if`，给枚举加一种类型会被悄悄吞掉，
#: 退出码 0、数字看着也对。`test_every_trade_type_has_a_handler` 钉住这张表
#: 与枚举同宽，免得日后有人只改枚举、忘了在这里补一行（比如做配股的时候）。
_HANDLERS: dict[TradeType, Callable[[Position, Transaction], None]] = {
    TradeType.BUY: _weighted_buy,
    TradeType.SELL: _sell,
    TradeType.FEE: _apply_fee,
    TradeType.DIVIDEND: _apply_dividend,
    TradeType.BONUS_SHARE: _apply_bonus_share,
}


def check_trade(pos: Position | None, tx: Transaction) -> None:
    """校验单笔交易在**当前持仓状态**下是否合法，非法则抛 TradeValidationError。

    独立于重放逻辑导出，便于写入路径在落库前单独调用。
    """
    held = pos.quantity if pos else 0.0
    if tx.trade_type in (TradeType.BUY, TradeType.SELL) and tx.quantity <= 0:
        raise TradeValidationError(
            f"{tx.symbol} 的{tx.trade_type.value}数量必须大于 0，当前为 {tx.quantity}"
        )
    if tx.trade_type is TradeType.BUY and tx.price < 0:
        raise TradeValidationError(f"{tx.symbol} 的买入单价不能为负，当前为 {tx.price}")
    if tx.trade_type is TradeType.SELL:
        if tx.price < 0:
            raise TradeValidationError(f"{tx.symbol} 的卖出单价不能为负，当前为 {tx.price}")
        # 这条校验此前缺失：卖出超过持有量会把数量算成负数，
        # 进而让总成本变成负数并被汇总悄悄吞掉（持仓在汇总时按数量<=0 跳过）。
        if tx.quantity > held:
            raise TradeValidationError(f"{tx.symbol} 卖出数量 {tx.quantity} 超过当时持有量 {held}")
    if tx.trade_type is TradeType.DIVIDEND:
        # 持股数与每股派息**两个都要**：金额是相乘得来的，缺一个就填不出金额。
        if tx.quantity <= 0:
            raise TradeValidationError(f"{tx.symbol} 分红的持股数必须大于 0，当前为 {tx.quantity}")
        if tx.price <= 0:
            raise TradeValidationError(f"{tx.symbol} 分红的每股派息必须大于 0，当前为 {tx.price}")
        if held <= 0:
            # 清仓之后才到账的分红确实存在，但账本上此刻没有持仓，摊薄无处可施；
            # 记成独立收益又要新开一处口径（且 `realized_pnl` 目前没有界面展示，
            # 记进去等于凭空消失）。宁可报错，让用户把日期记在持仓期间。
            raise TradeValidationError(
                f"{tx.symbol} 记分红时账本上没有持仓（当前 {held}）——"
                f"分红摊薄成本需要有持仓，请把日期记在持仓期间"
            )
    if tx.trade_type is TradeType.BONUS_SHARE:
        if tx.quantity <= 0:
            raise TradeValidationError(
                f"{tx.symbol} 的送股 / 转增股数必须大于 0，当前为 {tx.quantity}"
            )
        if tx.price != 0:
            raise TradeValidationError(
                f"{tx.symbol} 的送股 / 转增不涉及金额，单价必须为 0，当前为 {tx.price}"
            )
        if held <= 0:
            raise TradeValidationError(f"{tx.symbol} 记送股 / 转增时账本上没有持仓（当前 {held}）")
    if tx.fee < 0:
        raise TradeValidationError(f"{tx.symbol} 的费用不能为负，当前为 {tx.fee}")


def compute_positions(
    transactions: list[Transaction], *, strict: bool = False
) -> dict[str, Position]:
    """按标的对已排序交易序列做加权平均计算。

    若传入的 transactions 无序，需先自行排序（按 trade_date, id）。

    `strict=True` 时在重放过程中逐笔校验，遇到非法交易立即抛 TradeValidationError。
    写入账本前应当开启；**读取历史账本时必须关闭**——旧数据里可能已经存在越界记录，
    开启会导致整段历史读不出来。汇总服务靠 `quantity <= 0` 跳过这类脏数据。
    """
    positions: dict[str, Position] = {}
    for tx in transactions:
        pos = positions.setdefault(tx.symbol, Position(symbol=tx.symbol))
        if strict:
            check_trade(pos, tx)
        _HANDLERS[tx.trade_type](pos, tx)
    return positions


def holding_for(position: Position, current_price: float | None) -> Holding:
    """根据持仓与当前价计算盈亏与收益率。

    `current_price=None` 表示没有行情：市值、盈亏、盈亏率都是 `None`。
    **成本价不为正**时收益率同样无定义，一并给 `None`——比起一个看着像结论的
    `0.00%`，「算不出来」才是实话。成本价会被分红一路摊薄，长期持有足够久
    就会走到 0 甚至负数（券商 APP 也这么显示），而负分母算出来的
    `(现价 / 负成本 − 1)` 是个 -1000% 量级的怪数。**成本价本身照实显示**，
    只是不给那个假的收益率。
    """
    if current_price is None:
        return Holding(
            symbol=position.symbol,
            quantity=position.quantity,
            avg_cost=position.avg_cost,
            total_fees=position.total_fees,
        )
    market_value = position.quantity * current_price
    profit = (current_price - position.avg_cost) * position.quantity - position.total_fees
    rate = (current_price / position.avg_cost - 1) * 100 if position.avg_cost > 0 else None
    return Holding(
        symbol=position.symbol,
        quantity=position.quantity,
        avg_cost=position.avg_cost,
        total_fees=position.total_fees,
        current_price=current_price,
        market_value=market_value,
        profit=profit,
        profit_rate=rate,
    )


def summarize(positions: dict[str, Position]) -> dict[str, float]:
    """汇总所有持仓的总额、总成本、总费用与已实现盈亏。"""
    total_quantity_based_cost = sum(p.quantity * p.avg_cost for p in positions.values())
    return {
        "total_cost": sum(p.total_cost for p in positions.values()),
        "total_fees": sum(p.total_fees for p in positions.values()),
        "realized_pnl": sum(p.realized_pnl for p in positions.values()),
        "net_cost": total_quantity_based_cost,
    }


@dataclass
class FeeItem:
    """单笔费用的分项。"""

    symbol: str
    amount: float


def fee_breakdown(transactions: list[Transaction]) -> dict[str, float]:
    """按标的分项汇总累计费用（BUY/SELL/FEE 的费用均计入）。"""
    result: dict[str, float] = {}
    for tx in transactions:
        if tx.fee:
            result[tx.symbol] = result.get(tx.symbol, 0.0) + tx.fee
    return result
