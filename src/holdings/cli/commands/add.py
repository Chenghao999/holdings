"""holdings add 命令。"""

from __future__ import annotations

from datetime import date

import click

from holdings.models.enums import AssetType, MarketType, TradeType
from holdings.models.transaction import Transaction


@click.command()
@click.option("--symbol", required=True, help="标的代码")
@click.option("--market", required=True, help="市场：A股/美股/黄金")
@click.option("--type", "trade_type", required=True, help="类型：BUY/SELL/FEE")
@click.option("--qty", type=float, required=True, help="数量（FEE 类型填 0）")
@click.option("--price", type=float, required=True, help="单价（FEE 类型填 0）")
@click.option("--fee", type=float, default=0.0, help="费用（佣金、印花税、托管费等）")
@click.option("--date", "trade_date", default=None, help="交易日期 YYYY-MM-DD，默认今天")
@click.option("--group", default=None, help="组合分组")
@click.option("--notes", default=None, help="备注")
def add(
    symbol: str,
    market: str,
    trade_type: str,
    qty: float,
    price: float,
    fee: float,
    trade_date: str | None,
    group: str | None,
    notes: str | None,
) -> None:
    """新增一笔交易（含费用）。"""
    from holdings.storage import transaction_dao
    from holdings.utils.config import load_config

    cfg = load_config()
    tx = Transaction(
        symbol=symbol,
        market=MarketType(market),
        asset_type=_infer_asset_type(market),
        trade_date=date.fromisoformat(trade_date) if trade_date else date.today(),
        trade_type=TradeType(trade_type),
        quantity=qty,
        price=price,
        fee=fee,
        portfolio_group=group or cfg.default_group,
        notes=notes,
    )
    tx_id = transaction_dao.add(cfg.database_path, tx)
    click.echo(f"已新增交易 #{tx_id}: {symbol} {trade_type} qty={qty} fee={fee}")


def _infer_asset_type(market: str) -> AssetType:
    if market == MarketType.GOLD.value:
        return AssetType.GOLD
    return AssetType.STOCK
