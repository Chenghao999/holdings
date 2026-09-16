"""holdings sync 命令。"""

from __future__ import annotations

import click

from holdings.models.enums import MarketType

ALL_MARKETS = "全部"

# 缺任一必需依赖（如全市场都要求 yfinance）时明确告知，避免用户只看到一堆「失败」。
_REQUIRED_PACKAGES = ("yfinance", "akshare")


def _default_market() -> str:
    """`--market` 的默认值取自 `config.yaml` 的 `default_market`。

    用可调用默认值而不是在装饰器里直接求值：click 在**解析参数时**才调用它，
    那时才该去读配置；写在装饰器里等于在导入期读一次，而导入期根本不保证
    当前工作目录就是用户的项目目录（例如从别处 `holdings` 一下）。
    """
    from holdings.utils.config import load_config

    return load_config().default_market


@click.command()
@click.option(
    "--market",
    default=_default_market,
    type=click.Choice([m.value for m in MarketType] + [ALL_MARKETS]),
    help="市场",
)
def sync_cmd(market: str) -> None:
    """拉取最新价格并更新缓存。

    只要有一个标的同步成功就以退出码 0 结束；全部失败则返回 1，
    便于脚本据此判断（此前无论失败多少都返回 0）。
    """
    from rich.console import Console

    from holdings.exceptions import DataSourceUnavailableError
    from holdings.services.sync_service import sync
    from holdings.utils.config import load_config
    from holdings.utils.deps import is_installed

    cfg = load_config()
    console = Console()

    if market == ALL_MARKETS:
        markets = [MarketType.A_SHARE, MarketType.US_STOCK, MarketType.GOLD]
    else:
        markets = [MarketType(market)]

    updated = 0
    failed = 0
    for m in markets:
        result = sync(
            cfg.database_path,
            m,
            ttl_seconds=cfg.cache_ttl_seconds,
            timeout_seconds=cfg.sync_timeout_seconds,
        )
        for item in result.updated:
            console.print(
                f"[green]更新[/green] {item['symbol']}: {item['price']:.4f} ({item['source']})"
            )
        for item in result.failed:
            console.print(f"[red]失败[/red] {item['symbol']}: {item['error']}")
        updated += len(result.updated)
        failed += len(result.failed)

    if updated == 0 and failed == 0:
        console.print("没有需要同步的标的（可能均命中缓存）")
        return

    if updated == 0:
        missing = "、".join(p for p in _REQUIRED_PACKAGES if not is_installed(p))
        hint = "请安装数据源依赖 pip install 'holdings[data]'" + (
            f"（未安装：{missing}）" if missing else ""
        )
        # 抛异常而不是自己 SystemExit(1)：文案统一成「错误（1）：…」，
        # 与其它失败路径一致。顺带不再需要 escape()——那是给 Rich 的标记转义，
        # 而这条消息现在走 click.echo 输出，`[data]` 不会被吃掉。
        raise DataSourceUnavailableError(f"{failed} 个标的全部同步失败：{hint}")
