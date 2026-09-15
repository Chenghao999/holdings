"""绩效指标计算：年化收益、最大回撤、夏普比率（纯函数）。"""

from __future__ import annotations

import numpy as np


def max_drawdown(values: list[float]) -> float:
    """最大回撤 = (峰顶 - 谷底) / 峰顶，返回非负比例（0~1）。"""
    if not values:
        return 0.0
    arr = np.asarray(values, dtype=float)
    peak = np.maximum.accumulate(arr)
    drawdown = (peak - arr) / np.where(peak == 0, 1, peak)
    return float(np.max(drawdown)) if drawdown.size else 0.0


def annualized_return(start_value: float, end_value: float, years: float) -> float:
    """年化收益率（小数），years 为年数。"""
    if start_value <= 0 or years <= 0:
        return 0.0
    return (end_value / start_value) ** (1 / years) - 1


def sharpe_ratio(returns: list[float], risk_free_rate: float = 0.0) -> float:
    """夏普比率 = (日均收益 - 无风险) / 日收益标准差 × sqrt(252)。"""
    if len(returns) < 2:
        return 0.0
    arr = np.asarray(returns, dtype=float)
    excess = arr - risk_free_rate
    std = np.std(excess, ddof=1)
    if std == 0:
        return 0.0
    return float(np.mean(excess) / std * np.sqrt(252))
