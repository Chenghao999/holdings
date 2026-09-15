"""holdings add 命令。"""

from __future__ import annotations

from datetime import date

import click

from holdings.models.enums import AssetType, MarketType, TradeType
from holdings.models.transaction import Transaction


def _parse_trade_date(_ctx: click.Context, _param: click.Parameter, value: str | None) -> date:
    """把 YYYY-MM-DD 解析成 date；非法值交给 click 报错，避免裸 ValueError。

    定义在命令之前：装饰器在模块导入时求值，回调必须先存在。
    """
    if value is None:
        return date.today()
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise click.BadParameter(f"不是合法日期（应为 YYYY-MM-DD）：{value}") from None


def _infer_asset_type(market: str) -> AssetType:
    if market == MarketType.GOLD.value:
        return AssetType.GOLD
    return AssetType.STOCK


@click.command()
@click.option("--symbol", required=True, help="标的代码")
@click.option(
    "--market", required=True, type=click.Choice([m.value for m in MarketType]), help="市场"
)
@click.option(
    "--type",
    "trade_type",
    required=True,
    type=click.Choice([t.value for t in TradeType]),
    help="交易类型",
)
@click.option("--qty", type=float, required=True, help="数量（FEE 类型填 0）")
@click.option("--price", type=float, required=True, help="单价（FEE 类型填 0）")
@click.option("--fee", type=float, default=0.0, help="费用（佣金、印花税、托管费等）")
@click.option(
    "--date",
    "trade_date",
    default=None,
    callback=_parse_trade_date,
    help="交易日期 YYYY-MM-DD，默认今天",
)
@click.option("--group", default=None, help="组合分组")
@click.option("--notes", default=None, help="备注")
def add(
    symbol: str,
    market: str,
    trade_type: str,
    qty: float,
    price: float,
    fee: float,
    trade_date: date,
    group: str | None,
    notes: str | None,
) -> None:
    """新增一笔交易（含费用）。"""
    from holdings.services import trade_service
    from holdings.utils.config import load_config

    cfg = load_config()
    tx = Transaction(
        symbol=symbol,
        market=MarketType(market),
        asset_type=_infer_asset_type(market),
        trade_date=trade_date,
        trade_type=TradeType(trade_type),
        quantity=qty,
        price=price,
        fee=fee,
        portfolio_group=group or cfg.default_group,
        notes=notes,
    )
    # 经 trade_service 而非直接写 DAO：落库前会结合历史持仓校验
    # （卖出不得超过持有、数量与费用不得为负），失败时抛 TradeValidationError → 退出码 5。
    tx_id = trade_service.add_transaction(cfg.database_path, tx)
    click.echo(f"已新增交易 #{tx_id}: {symbol} {trade_type} qty={qty} fee={fee}")
