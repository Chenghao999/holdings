"""网络调用的超时与重试设置：不让 `sync` 无限挂起。

`akshare` 与 `yfinance` 都没有可靠的超时手段（akshare 压根没有这个参数），
上游一旦不响应，`holdings sync` 会一直卡在那里，用户只能 Ctrl-C。
这里用「放进守护线程 + 到点就放弃等待」兜底。

**超时的语义是「放弃等待」，不是「取消请求」。** Python 没有安全的线程取消
机制，被放弃的那个请求仍会在后台跑到它自己结束。这无法绕开，但守护线程
不会拖住进程退出——CLI 因此能及时返回、把该标的记成失败，而不是挂死。
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any, TypeVar

from holdings.exceptions import DataSourceUnavailableError
from holdings.utils.config import DEFAULT_CONFIG

T = TypeVar("T")

#: 默认值从配置层取，不在这里另写一份——抄出来的那份迟早和 CONFIG_SPEC 对不上。
DEFAULT_TIMEOUT_SECONDS = DEFAULT_CONFIG["sync"]["timeout_seconds"]


def call_with_timeout(func: Callable[..., T], seconds: float, *args: Any, **kwargs: Any) -> T:
    """在守护线程里执行 `func`，超过 `seconds` 秒仍未返回就放弃。

    `seconds <= 0` 表示不限时（配置里写 0 的用户要的就是「别管我」）。
    超时抛 `DataSourceUnavailableError`：调用方据此把该标的记成失败，
    而不是让整条命令卡住——这正是「超时」与「崩溃」的区别。
    """
    if seconds <= 0:
        return func(*args, **kwargs)

    result: list[T] = []
    failure: list[Exception] = []

    def _run() -> None:
        try:
            result.append(func(*args, **kwargs))
        except Exception as exc:  # 原样带回主线程，保持异常类型与调用方约定一致
            failure.append(exc)

    thread = threading.Thread(target=_run, name="holdings-fetch", daemon=True)
    thread.start()
    thread.join(seconds)

    if thread.is_alive():
        raise DataSourceUnavailableError(f"拉取超过 {seconds:g} 秒仍未返回，已放弃等待")
    if failure:
        raise failure[0]
    return result[0]
