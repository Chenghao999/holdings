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
@click.option(
    "--flow",
    type=float,
    default=0.0,
    help="上次快照之后的净入金：入金为正、出金为负（基准对比据此剔除现金流）",
)
@click.option("--note", default=None, help="备注")
def snapshot_cmd(
    total: float,
    equity: float,
    gold: float,
    cash: float,
    snap_date: str | None,
    flow: float,
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
        external_flow=flow,
        note=note,
    )
    snap_id = snapshot_service.record(cfg.database_path, snap)
    # 净入金非 0 时回显一句：手记的数字最容易被记反（出入金方向），
    # 当场看见自己填的是正是负，比事后再去 `holdings snapshots` 里找便宜。
    flow_note = f"净入金 {flow:+,.2f}" if flow else ""
    tail = "；".join(part for part in (flow_note, note) if part)
    click.echo(f"已记录快照 #{snap_id}" + (f"（{tail}）" if tail else ""))
