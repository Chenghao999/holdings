"""holdings snapshot 命令：记录资产快照。"""

from __future__ import annotations

from datetime import date

import click

from holdings.models.snapshot import Snapshot


@click.command()
@click.option("--total", type=float, required=True, help="总资产")
@click.option("--equity", type=float, default=0.0, help="权益类资产")
@click.option("--gold", type=float, default=0.0, help="黄金资产")
@click.option("--cash", type=float, default=0.0, help="现金余额")
@click.option("--date", "snap_date", default=None, help="快照日期 YYYY-MM-DD，默认今天")
@click.option("--note", default=None, help="备注")
def snapshot_cmd(
    total: float,
    equity: float,
    gold: float,
    cash: float,
    snap_date: str | None,
    note: str | None,
) -> None:
    """记录当前时间点总资产快照。"""
    from holdings.services import snapshot_service
    from holdings.utils.config import load_config

    cfg = load_config()
    snap = Snapshot(
        snapshot_date=date.fromisoformat(snap_date) if snap_date else date.today(),
        total_value=total,
        equity_value=equity,
        gold_value=gold,
        cash_balance=cash,
        note=note,
    )
    snap_id = snapshot_service.record(cfg.database_path, snap)
    click.echo(f"已记录快照 #{snap_id}" + (f"（{note}）" if note else ""))
