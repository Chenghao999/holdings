"""汇率换算（预留）。MVP 阶段不实现多币种换算，仅提供占位接口。"""

from __future__ import annotations


def convert(amount: float, from_currency: str, to_currency: str) -> float:
    """将金额从一种货币换算到另一种货币。

    当前为占位实现：仅处理同币种，跨币种抛 NotImplementedError。
    """
    if from_currency == to_currency:
        return amount
    raise NotImplementedError("多币种汇率换算将在后续版本实现")
