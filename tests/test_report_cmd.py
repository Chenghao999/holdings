"""`holdings report` 的绩效行渲染。

锁住两件事：一是 BACKLOG B-02 的判据「100/120/90/110 显示 25.00%」，
二是**算不出来时显示 `—` 而不是 0**——后者才是这一项真正要防的回归，
因为 `0.00%` 的回撤和 `0.00` 的夏普看起来都像是正常的结论。
"""

from __future__ import annotations

from datetime import date

import pytest

from holdings.cli.commands import report as report_module
from holdings.cli.renderers.table_renderer import render_performance_line
from holdings.models.snapshot import Snapshot
from holdings.services.report_service import PerformanceSummary, get_performance
from holdings.storage import snapshot_dao


def _add_snaps(db_path: str, *rows: tuple[int, int, float]) -> None:
    """rows 为 (月, 日, 净值)。"""
    for month, day, total in rows:
        snapshot_dao.add(
            db_path,
            Snapshot(
                snapshot_date=date(2025, month, day),
                total_value=total,
                equity_value=total,
                gold_value=0.0,
            ),
        )


@pytest.fixture
def use_db(db_path, monkeypatch):
    """把命令内部的 load_config 指向临时库。"""

    class _Cfg:
        database_path = db_path

    monkeypatch.setattr("holdings.utils.config.load_config", lambda *a, **k: _Cfg())
    return db_path


# ------------------------------------------------------------------ 渲染层


def test_line_shows_the_known_drawdown():
    perf = PerformanceSummary(
        snapshot_count=4,
        max_drawdown=0.25,
        annualized_return=0.1,
        sharpe=1.5,
        first_date=date(2025, 1, 1),
        last_date=date(2025, 4, 1),
    )

    line = render_performance_line(perf)

    assert "最大回撤 25.00%" in line
    assert "年化收益 10.00%" in line
    assert "夏普 1.50" in line


def test_line_renders_unknown_metrics_as_dash_not_zero():
    perf = PerformanceSummary(snapshot_count=4, max_drawdown=0.25)

    line = render_performance_line(perf)

    assert "年化收益 —" in line
    assert "夏普 —" in line
    assert "0.00" not in line.split("最大回撤")[1], "算不出来的指标不能渲染成 0"


def test_line_explains_why_a_metric_is_missing():
    """只印 `—` 会让用户以为是程序坏了，原因要跟在后面。"""
    perf = PerformanceSummary(
        snapshot_count=4,
        max_drawdown=0.25,
        notes=["快照间隔不规律，夏普不做折算"],
    )

    assert "快照间隔不规律" in render_performance_line(perf)


def test_line_states_the_reason_when_there_are_too_few_snapshots():
    perf = PerformanceSummary(snapshot_count=1)

    line = render_performance_line(perf)

    assert "快照不足" in line
    assert "1 条" in line


# ------------------------------------------------------------------ 命令层


def test_report_shows_drawdown_from_snapshots(use_db, capsys):
    """BACKLOG B-02 的端到端判据。"""
    _add_snaps(use_db, (1, 1, 100.0), (2, 1, 120.0), (3, 1, 90.0), (4, 1, 110.0))

    report_module.report_cmd.callback(verbose=False)

    out = capsys.readouterr().out
    assert "最大回撤 25.00%" in out


def test_report_without_snapshots_says_so_instead_of_printing_zeros(use_db, capsys):
    """没记过快照是常态，不能因此显示「回撤 0.00%」。"""
    report_module.report_cmd.callback(verbose=False)

    out = capsys.readouterr().out
    assert "快照不足" in out
    assert "最大回撤" not in out


def test_report_verbose_still_renders_the_extra_tables(use_db, capsys):
    _add_snaps(use_db, (1, 1, 100.0), (2, 1, 120.0))

    report_module.report_cmd.callback(verbose=True)

    out = capsys.readouterr().out
    assert "费用分项" in out
    assert "资产配置占比" in out


def test_get_performance_is_wired_into_the_report_command(use_db, capsys, monkeypatch):
    """绩效行的数据必须真的来自 snapshots，而不是渲染层另算一份。"""
    _add_snaps(use_db, (1, 1, 100.0), (2, 1, 120.0), (3, 1, 90.0), (4, 1, 110.0))
    seen = {}

    def _spy(db_path):
        seen["called_with"] = db_path
        return get_performance(db_path)

    monkeypatch.setattr("holdings.services.report_service.get_performance", _spy)
    report_module.report_cmd.callback(verbose=False)

    assert seen["called_with"] == use_db
