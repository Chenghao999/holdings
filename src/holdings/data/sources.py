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
from typing import TypeVar

from holdings.data import resilience
from holdings.exceptions import DataSourceUnavailableError, HoldingsError
from holdings.models.enums import MarketType
from holdings.utils.config import DEFAULT_CONFIG

#: 两次尝试之间的退避秒数。
RETRY_BACKOFF_SECONDS = 0.5

_T = TypeVar("_T")

#: 一个数据源：给代码，取回一样东西。取什么由调用方定——报价与标的资料
#: 共用这套降级，所以这里不能写死成 `PriceResult`。
Source = Callable[[str], _T]

#: 取价的优先级键（`data_sources.priority`）。
PRICE_PRIORITY_KEY = "priority"
#: 取标的资料的优先级键。与取价分开配，因为**能报价的源不一定知道这标的叫什么**
#: （例如给美股配的源未必认得 A 股代码），硬绑成一份会让用户没法单独调。
INSTRUMENT_PRIORITY_KEY = "instrument_priority"


def priority_for(market: MarketType, key: str = PRICE_PRIORITY_KEY) -> list[str]:
    """该市场在 `key` 这一项下的数据源顺序。

    读不到配置时回落到 `DEFAULT_CONFIG` 里的内置顺序——默认值只存在配置层
    一处，这里不另抄一份，免得两边悄悄分叉。配置写成一个空列表或非列表时
    同样回落：那多半是手写时的笔误，按默认顺序跑比整个同步失败有用。
    """
    builtin = DEFAULT_CONFIG["data_sources"].get(key, {}).get(market.value, [])
    try:
        from holdings.utils.config import load_config

        configured = load_config().data_sources.get(key, {}).get(market.value)
    except (HoldingsError, OSError):
        return list(builtin)
    if not isinstance(configured, list) or not configured:
        return list(builtin)
    return [str(name) for name in configured]


def fetch_with_fallback(
    symbol: str,
    market: MarketType,
    sources: dict[str, Source[_T]],
    unavailable_message: str,
    order: list[str] | None = None,
    key: str = PRICE_PRIORITY_KEY,
) -> _T:
    """按顺序逐个数据源尝试，各自带 `sync.retry_count` 次重试。

    `sources` 是该市场**实现得出来**的源；配置里列了但这里没有的（例如给美股
    配了 `akshare`）会被跳过，而不是报错——上游库的能力边界不该由用户来记。
    真正的问题（配的源一个都没有）会明确指出，不让人对着「数据源不可用」猜。

    返回类型随 `sources` 走：取价回 `PriceResult`，取标的资料回 `SymbolInfo`，
    两者的重试与降级行为因此是同一条代码路径。

    `key` 决定不传 `order` 时读哪一项配置（`data_sources.priority` 还是
    `data_sources.instrument_priority`）。

    显式传入 `order` 时不读配置。这条通道是给黄金留的：它的两个源是两种
    **不同的标的**（国内现货/ETF 与国际 GC=F），不是彼此的备份，不能按优先级
    互相回退——详见 `gold.py` 里的说明。
    """
    order = priority_for(market, key) if order is None else list(order)
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
    # 到这里 `last_err` 一定是个异常：`usable` 上面已拦掉空表，而
    # `retry_count()` 是 `max(0, …)`，所以内层循环至少跑一次。
    # 写成断言而不是 `if last_err is None`：那是够不到的分支（B-12 清过的死代码），
    # 而断言把「这个不变式被谁破坏了」当场喊出来。
    assert last_err is not None, "降级链没跑过就在报失败原因——这段代码坏了"
    raise DataSourceUnavailableError(_with_reason(unavailable_message, last_err)) from last_err


def _with_reason(message: str, err: BaseException) -> str:
    """把链条末端那个异常接到消息末尾——**降级链的兜底捕获不能把真因吃掉**。

    那三个处境（没装包 / 网络不通 / 自己代码写错）在用户眼里长着同一张脸，
    而**修法完全不同**：一个 `pip install`，一个查网络，一个报 issue。B-36 就是
    被这张脸挡住的——`GC=F` 次次失败，报的是「数据源不可用」，真因是一个
    和我们无关的 `TypeError`（签名写错），用户拿着那句话去重装了 yfinance。

    自己抛的那几个（`HoldingsError`）本来就是人话（`未安装 akshare`），直接用；
    外面来的异常要**带上类型名**，因为 `str()` 有时只是个括号包着的元组
    （`('Connection aborted.', RemoteDisconnected(...))`），光看内容分不出
    「网络断了」还是「我这段代码写错了」。

    这与 DAO 里 `f"…：{exc}"` 的写法不同，那里永远是 `sqlite3.Error`，
    类型名一个字符的信息量都没有。
    """
    reason = str(err) if isinstance(err, HoldingsError) else _typed(err)
    return f"{message}；底层错误：{reason}" if reason else message


def _typed(err: BaseException) -> str:
    """外来异常 → `类型名: 消息`；连消息都没有就只留类型名。"""
    text = str(err)
    return f"{type(err).__name__}: {text}" if text else type(err).__name__
