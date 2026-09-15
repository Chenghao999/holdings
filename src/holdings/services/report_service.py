"""报表绩效指标服务：把资产快照折算成回撤 / 年化收益 / 夏普。

与 `portfolio_service` 的分工：那边从**交易流水**算持仓成本与盈亏，
这边从**资产快照**算组合层面的绩效。两者互不依赖，`report` 命令分别取用。

这一层最重要的约定是「宁可显示 `—`，不给一个错的数」：快照由用户手记，
间隔不规律、条数可能只有一两条，凡是口径不成立的情形一律返回 `None`，
由渲染层显示 `—`。判断依据都写在下面各自的注释里。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from itertools import pairwise

from holdings.portfolio import metrics
from holdings.storage import snapshot_dao

# 年化收益要求的最小跨度（天）。相隔一天的两次快照能外推出天文数字的
# 年化收益——数学上成立，决策上无用，还会让报表看起来像出了故障。
MIN_DAYS_FOR_ANNUALIZED = 30


@dataclass
class PerformanceSummary:
    """组合层面的绩效指标，纯数据。

    三个指标都是 `None` 时表示「快照不足或口径不成立」，渲染层显示 `—`，
    不要把它当成 0——`0.00%` 的回撤看着像结论，实际只是没有第二个数据点。
    """

    snapshot_count: int
    max_drawdown: float | None = None  # 0~1 的比例
    annualized_return: float | None = None  # 小数
    sharpe: float | None = None
    first_date: date | None = None
    last_date: date | None = None
    # 每一条 `—` 的原因，渲染层直接展示。理由放在这里而不是渲染层：
    # 「为什么这个数算不出来」是口径决定，跟着上面那些判断走才不会两边打架。
    notes: list[str] = field(default_factory=list)


def get_performance(db_path: str) -> PerformanceSummary:
    """读取全部快照并计算绩效指标，不输出任何文字。"""
    snaps = snapshot_dao.get_all(db_path)
    if len(snaps) < 2:
        # 单点算出来的「最大回撤 0.00%」看着像结论，其实只是没有第二个点可比。
        return PerformanceSummary(snapshot_count=len(snaps))

    values = [s.total_value for s in snaps]
    gaps = [(b.snapshot_date - a.snapshot_date).days for a, b in pairwise(snaps)]
    span_days = sum(gaps)

    returns, usable_gaps = metrics.return_series(values, gaps)
    periods = metrics.periods_per_year(usable_gaps)

    # 起点净值为 0 时年化收益无定义（收益率整体不成立），与跨度不足一并归为 None。
    notes: list[str] = []
    if values[0] <= 0:
        notes.append("首条快照净值为 0，年化收益无定义")
        annualized = None
    elif span_days < MIN_DAYS_FOR_ANNUALIZED:
        notes.append(f"首末快照跨度不足 {MIN_DAYS_FOR_ANNUALIZED} 天，年化收益无意义")
        annualized = None
    else:
        annualized = metrics.annualized_return(
            values[0], values[-1], span_days / metrics.DAYS_PER_YEAR
        )

    if periods is None:
        notes.append("快照间隔不规律，夏普不做折算")

    return PerformanceSummary(
        snapshot_count=len(snaps),
        max_drawdown=metrics.max_drawdown(values),
        annualized_return=annualized,
        # periods 为 None 即「间隔不规律」，此时不算夏普。它不是 0，是「不知道」。
        sharpe=metrics.sharpe_ratio(returns, periods) if periods else None,
        first_date=snaps[0].snapshot_date,
        last_date=snaps[-1].snapshot_date,
        notes=notes,
    )
