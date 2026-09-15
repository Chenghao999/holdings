"""绩效指标计算：年化收益、最大回撤、夏普比率（纯函数）。

本模块只认识数值，不认识日期与数据库：快照是「用户手记、间隔不规律」的，
把间隔信息折算成采样频率是 `periods_per_year` 的职责，它同样只吃一个整数序列
（相邻两点的间隔天数），因此这一层依然是零 IO 的纯函数。
"""

from __future__ import annotations

import numpy as np

# 一年按 365.25 天算：闰年摊到每年是 0.25 天，用 365 会让跨闰年的跨度少算一天。
DAYS_PER_YEAR = 365.25


def max_drawdown(values: list[float]) -> float:
    """最大回撤 = (峰顶 - 谷底) / 峰顶，返回非负比例（0~1）。

    取全局最大值而非首个回撤：`[100, 80, 120, 72]` 的答案是 40%（120→72），
    不是前面那个 20%。空序列与单点返回 0.0。
    """
    if not values:
        return 0.0
    arr = np.asarray(values, dtype=float)
    peak = np.maximum.accumulate(arr)
    drawdown = (peak - arr) / np.where(peak == 0, 1, peak)
    return float(np.max(drawdown)) if drawdown.size else 0.0


def annualized_return(start_value: float, end_value: float, years: float) -> float:
    """年化收益率（小数），years 为年数。

    跨度必须用首末快照的**真实天数**折算，不要拿 `len(snapshots) / 252` 顶替——
    快照间隔不等距，那样算出来的不是年化。
    """
    if start_value <= 0 or years <= 0:
        return 0.0
    return (end_value / start_value) ** (1 / years) - 1


def return_series(values: list[float], gaps_days: list[int]) -> tuple[list[float], list[int]]:
    """由净值序列与相邻间隔，返回一一对应的「收益率序列 + 间隔序列」。

    两件事在同一个函数里做，是因为它们必须**等长**：夏普的年化系数来自间隔，
    收益来自净值，错位一格算出来的数与事实无关。

    前一个点净值为 0 时该段收益率无定义，此时把这一段（收益率与间隔）**成对丢弃**，
    而不是塞一个 0 进去假装有收益，也不返回 `inf` 污染后面的均值与标准差。
    """
    returns: list[float] = []
    gaps: list[int] = []
    # strict=False：间隔序列比净值短时按最短的截断，不抛异常——
    # 这里的入参来自数据库，宁可少算一段也不要因为长度对不上整个报表崩掉。
    for prev, curr, gap in zip(values, values[1:], gaps_days, strict=False):
        if prev == 0:
            continue
        returns.append(curr / prev - 1)
        gaps.append(gap)
    return returns, gaps


def periods_per_year(gaps_days: list[int], *, tolerance: float = 0.25) -> float | None:
    """把相邻两点的间隔天数折算成「每年多少个周期」；间隔不规律时返回 None。

    夏普要乘一个年化系数，这个系数只有在**采样频率恒定**时才有意义。
    快照由用户手记，间隔可能忽长忽短（今天记一次、下个月记三次），
    此时把每段收益当成同频采样会算出一个没有意义的数——那比不显示更糟。

    判据是间隔的变异系数（样本标准差 / 均值）不超过 `tolerance`，默认 0.25，
    即各段间隔与平均间隔的偏离在 ±25% 以内：月度快照的 28~31 天（CV≈0.04）、
    每周快照的 7 天都远在阈值内，而漏记一周（7/7/14）会超出，如实判为不规律。
    少于 2 段间隔时样本标准差无定义，同样返回 None。
    """
    if len(gaps_days) < 2 or any(g <= 0 for g in gaps_days):
        # 间隔为 0 只可能来自同一日期的两条快照，库里有 UNIQUE 约束挡着；
        # 这里仍显式拒绝，免得将来约束被放宽后算出 inf 的周期数。
        return None
    # 上面的 any(g <= 0) 已保证均值必为正，这里不再重复判一次。
    mean_gap = float(np.mean(gaps_days))
    if float(np.std(gaps_days, ddof=1)) / mean_gap > tolerance:
        return None
    return DAYS_PER_YEAR / mean_gap


def sharpe_ratio(
    returns: list[float],
    periods_per_year: float,
    risk_free_rate: float = 0.0,
) -> float:
    """夏普比率 = (每期平均超额收益 / 每期收益标准差) × sqrt(periods_per_year)。

    `periods_per_year` 是**必填**的：它取决于入参的采样频率，日收益是 252、
    月收益约 12、周收益约 52。此前这里硬编码 `sqrt(252)`，等于默认所有调用方
    传的都是日收益——而快照间隔根本不规律，一旦有人直接把快照收益喂进来，
    得到的是一个乘以 15.87 的假数。改成必填后，调用方必须显式说明口径，
    而「拿不到可靠口径」的情形（见 `periods_per_year`）应当在调用方就显示 `—`。

    收益序列少于 2 个点、或全程零波动时返回 0.0（无波动即无风险调整收益）；
    `periods_per_year` 非正则是调用方算错了口径，直接抛 `ValueError`——
    这种时候返回 0.0 会在报表上印出一个看着像结论的假数字。
    """
    if periods_per_year <= 0:
        raise ValueError(f"periods_per_year 必须为正，当前为 {periods_per_year}")
    if len(returns) < 2:
        return 0.0
    arr = np.asarray(returns, dtype=float)
    excess = arr - risk_free_rate
    std = np.std(excess, ddof=1)
    if std == 0:
        return 0.0
    return float(np.mean(excess) / std * np.sqrt(periods_per_year))
