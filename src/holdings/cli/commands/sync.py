"""holdings sync 命令。"""

from __future__ import annotations

import click

from holdings.models.enums import MarketType


@click.command()
@click.option("--market", default="全部", help="市场：A股/美股/黄金/全部")
def sync_cmd(market: str) -> None:
    """拉取最新价格并更新缓存。"""
    from rich.console import Console

    from holdings.services.sync_service import sync
    from holdings.utils.config import load_config

    cfg = load_config()
    console = Console()

    if market == "全部":
        markets = [MarketType.A_SHARE, MarketType.US_STOCK, MarketType.GOLD]
    else:
        markets = [MarketType(market)]

    for m in markets:
        result = sync(cfg.database_path, m, ttl_seconds=cfg.cache_ttl_seconds)
        for item in result.updated:
            console.print(
                f"[green]更新[/green] {item['symbol']}: {item['price']:.4f} ({item['source']})"
            )
        for item in result.failed:
            console.print(f"[red]失败[/red] {item['symbol']}: {item['error']}")
