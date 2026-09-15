"""数据源优先级：按 `data_sources.priority` 依次尝试取价。

配置项 `data_sources.priority` 此前无人读取——降级顺序硬编码在 `a_stock.py` 里
（`akshare` 失败就换 `yfinance`），用户把它改成 `[yfinance, akshare]` 不会有
任何变化。这里把它接上：每个市场声明「自己有哪些源可用」，**顺序由配置决定**。

所有市场共用同一套重试与降级逻辑，不再各写一份：此前只有 A 股有重试，
美股与黄金一次失败就结束，那是实现分散带来的偶然差异，不是有意的设计。
"""

from __future__ import annotations

import time
from collections.abc import Callable

from holdings.data import resilience
from holdings.data.fetcher import PriceResult
from holdings.exceptions import DataSourceUnavailableError, HoldingsError
from holdings.models.enums import MarketType
from holdings.utils.config import DEFAULT_CONFIG

#: 两次尝试之间的退避秒数。
RETRY_BACKOFF_SECONDS = 0.5

Source = Callable[[str], PriceResult]


def priority_for(market: MarketType) -> list[str]:
    """该市场的数据源顺序。

    读不到配置时回落到 `DEFAULT_CONFIG` 里的内置顺序——默认值只存在配置层
    一处，这里不另抄一份，免得两边悄悄分叉。配置写成一个空列表或非列表时
    同样回落：那多半是手写时的笔误，按默认顺序跑比整个同步失败有用。
    """
    builtin = DEFAULT_CONFIG["data_sources"]["priority"].get(market.value, [])
    try:
        from holdings.utils.config import load_config

        configured = load_config().data_sources.get("priority", {}).get(market.value)
    except (HoldingsError, OSError):
        return list(builtin)
    if not isinstance(configured, list) or not configured:
        return list(builtin)
    return [str(name) for name in configured]


def fetch_with_fallback(
    symbol: str,
    market: MarketType,
    sources: dict[str, Source],
    unavailable_message: str,
    order: list[str] | None = None,
) -> PriceResult:
    """按顺序逐个数据源尝试，各自带 `sync.retry_count` 次重试。

    `sources` 是该市场**实现得出来**的源；配置里列了但这里没有的（例如给美股
    配了 `akshare`）会被跳过，而不是报错——上游库的能力边界不该由用户来记。
    真正的问题（配的源一个都没有）会明确指出，不让人对着「数据源不可用」猜。

    显式传入 `order` 时不读配置。这条通道是给黄金留的：它的两个源是两种
    **不同的标的**（国内现货/ETF 与国际 GC=F），不是彼此的备份，不能按优先级
    互相回退——详见 `gold.py` 里的说明。
    """
    order = priority_for(market) if order is None else list(order)
    usable = [name for name in order if name in sources]
    if not usable:
        raise DataSourceUnavailableError(
            f"{market.value}在配置里指定的数据源都不可用：{'、'.join(order) or '（空）'}"
        )

    last_err: Exception | None = None
    for name in usable:
        source = sources[name]
        for attempt in range(resilience.retry_count() + 1):
            if attempt:
                # 退避放在**重试之前**：写在 except 末尾会让最后一次失败之后
                # 还白等一次，用户多等半秒却什么也没等到。
                time.sleep(RETRY_BACKOFF_SECONDS)
            try:
                return source(symbol)
            except Exception as exc:  # 降级要捕获所有异常：任何一种都不该中断取价
                last_err = exc
    raise DataSourceUnavailableError(unavailable_message) from last_err
