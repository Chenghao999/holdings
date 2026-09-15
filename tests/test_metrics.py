"""`portfolio/metrics.py` 的纯函数测试。

这一层此前 0% 覆盖——一个写完了从没被调用过的模块，也就从没被验证过。
下面按「空序列 / 单点 / 单调上涨 / 单调下跌 / 已知回撤」这几类边界来锁。
"""

from __future__ import annotations

import pytest

from holdings.portfolio import metrics

# --------------------------------------------------------------- max_drawdown


def test_max_drawdown_of_empty_series_is_zero():
    assert metrics.max_drawdown([]) == 0.0


def test_max_drawdown_of_single_point_is_zero():
    assert metrics.max_drawdown([100.0]) == 0.0


def test_max_drawdown_is_zero_when_never_below_a_peak():
    """全涨（含持平）时没有任何回撤。"""
    assert metrics.max_drawdown([100.0, 110.0, 130.0, 130.0]) == 0.0


def test_max_drawdown_of_known_series():
    """BACKLOG B-02 的判据：(120 - 90) / 120 = 25%。"""
    assert metrics.max_drawdown([100.0, 120.0, 90.0, 110.0]) == pytest.approx(0.25)


def test_max_drawdown_takes_the_global_maximum_not_the_first_dip():
    """先跌 20% 再涨回更高、然后跌 40%：答案是 40%，不是 20%。"""
    assert metrics.max_drawdown([100.0, 80.0, 120.0, 72.0]) == pytest.approx(0.4)


def test_max_drawdown_of_full_wipeout_is_one():
    assert metrics.max_drawdown([100.0, 50.0, 0.0]) == pytest.approx(1.0)


def test_max_drawdown_when_series_starts_at_zero():
    """起点为 0 时比值无定义，按 0 处理而不是除零崩掉。"""
    assert metrics.max_drawdown([0.0, 0.0, 5.0]) == 0.0


# --------------------------------------------------------- annualized_return


def test_annualized_return_of_one_year_equals_simple_return():
    assert metrics.annualized_return(100.0, 110.0, 1.0) == pytest.approx(0.10)


def test_annualized_return_compounds_over_two_years():
    """两年翻倍 → sqrt(2) - 1 ≈ 41.42%，不是 100%。"""
    assert metrics.annualized_return(100.0, 200.0, 2.0) == pytest.approx(0.41421356)


def test_annualized_return_handles_a_loss():
    assert metrics.annualized_return(100.0, 50.0, 1.0) == pytest.approx(-0.5)


@pytest.mark.parametrize(("start", "years"), [(0.0, 1.0), (-1.0, 1.0), (100.0, 0.0), (100.0, -1.0)])
def test_annualized_return_is_zero_when_undefined(start, years):
    """起点非正或跨度为 0 时收益率无定义，返回 0.0 而不是 inf / ZeroDivisionError。"""
    assert metrics.annualized_return(start, 200.0, years) == 0.0


# ------------------------------------------------------------- return_series


def test_return_series_of_empty_and_single_point_is_empty():
    assert metrics.return_series([], []) == ([], [])
    assert metrics.return_series([100.0], []) == ([], [])


def test_return_series_pairs_each_return_with_its_own_gap():
    """收益与间隔必须一一对应，错位一格算出来的夏普与事实无关。"""
    returns, gaps = metrics.return_series([100.0, 110.0, 99.0], [30, 31])

    assert returns == pytest.approx([0.10, -0.10])
    assert gaps == [30, 31]


def test_return_series_drops_the_segment_that_starts_from_zero():
    """前一点为 0 时该段收益无定义，收益率与间隔成对丢弃，而不是记成 0。"""
    returns, gaps = metrics.return_series([0.0, 100.0, 110.0], [30, 31])

    assert returns == pytest.approx([0.10])
    assert gaps == [31], "间隔必须跟着收益率一起丢，否则两者不再对齐"


# ----------------------------------------------------------- periods_per_year


def test_periods_per_year_needs_at_least_two_intervals():
    """只有一个间隔时样本标准差无定义，不给数。"""
    assert metrics.periods_per_year([]) is None
    assert metrics.periods_per_year([30]) is None


def test_periods_per_year_accepts_a_monthly_series():
    """月度快照的 28~31 天波动很小，应判为规律。"""
    gaps = [31, 28, 31, 30, 31, 30]

    assert metrics.periods_per_year(gaps) == pytest.approx(365.25 / (sum(gaps) / len(gaps)))


def test_periods_per_year_accepts_a_weekly_series():
    assert metrics.periods_per_year([7, 7, 7, 7]) == pytest.approx(365.25 / 7)


def test_periods_per_year_rejects_a_missed_interval():
    """漏记一周（7/7/14）改变了采样频率，不该硬算夏普。"""
    assert metrics.periods_per_year([7, 7, 14]) is None


def test_periods_per_year_rejects_wildly_uneven_intervals():
    assert metrics.periods_per_year([7, 14]) is None


def test_periods_per_year_tolerance_is_adjustable():
    """放宽到 0.5 时 7/14 的变异系数 0.47 就在阈值内了。"""
    assert metrics.periods_per_year([7, 14], tolerance=0.5) == pytest.approx(365.25 / 10.5)


def test_periods_per_year_rejects_non_positive_gap():
    """间隔为 0 会让周期数变成 inf，显式拒绝。"""
    assert metrics.periods_per_year([0, 30]) is None
    assert metrics.periods_per_year([-1, 30]) is None


# -------------------------------------------------------------- sharpe_ratio


def test_sharpe_ratio_needs_at_least_two_returns():
    assert metrics.sharpe_ratio([], 252) == 0.0
    assert metrics.sharpe_ratio([0.01], 252) == 0.0


def test_sharpe_ratio_of_constant_returns_is_zero():
    """零波动即没有风险调整后的超额收益可算。"""
    assert metrics.sharpe_ratio([0.01, 0.01, 0.01], 252) == 0.0


def test_sharpe_ratio_known_value_for_daily_returns():
    assert metrics.sharpe_ratio([0.01, -0.01, 0.02], 252) == pytest.approx(6.92820323027551)


def test_sharpe_ratio_scales_with_the_sampling_period():
    """同一组收益，按月折算与按日折算的差别只在年化系数上。"""
    daily = metrics.sharpe_ratio([0.01, -0.01, 0.02], 252)
    monthly = metrics.sharpe_ratio([0.01, -0.01, 0.02], 12)

    assert monthly == pytest.approx(daily * (12 / 252) ** 0.5)


def test_sharpe_ratio_subtracts_the_risk_free_rate_per_period():
    """无风险利率是**每期**口径：减掉之后波动未变、均值下降，夏普随之变小。"""
    without = metrics.sharpe_ratio([0.05, -0.01, 0.03], 252)
    with_rf = metrics.sharpe_ratio([0.05, -0.01, 0.03], 252, risk_free_rate=0.02)

    assert with_rf < without


def test_sharpe_ratio_rejects_a_non_positive_period_count():
    """口径算错时抛错，而不是返回 0.0 在报表上印一个看着像结论的假数字。"""
    with pytest.raises(ValueError, match="periods_per_year"):
        metrics.sharpe_ratio([0.01, -0.01], 0)


def test_days_per_year_matches_the_annualization_used_by_years():
    """两处折算系数必须是同一个，否则年化与周期数会各算各的。"""
    assert metrics.DAYS_PER_YEAR == 365.25
