"""`holdings report` 的绩效行渲染。

锁住两件事：一是 BACKLOG B-02 的判据「100/120/90/110 显示 25.00%」，
二是**算不出来时显示 `—` 而不是 0**——后者才是这一项真正要防的回归，
因为 `0.00%` 的回撤和 `0.00` 的夏普看起来都像是正常的结论。
"""

from __future__ import annotations

from datetime import date

import click
import pytest

from holdings.cli.commands import report as report_module
from holdings.cli.renderers.table_renderer import render_performance_line
from holdings.models.snapshot import Snapshot
from holdings.services import report_service
from holdings.services.report_service import PerformanceSummary, get_performance
from holdings.storage import price_cache_dao, snapshot_dao, transaction_dao


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


# --------------------------------------------------------------- 分组报表（B-21）


def _two_groups(db_path, make_tx) -> None:
    transaction_dao.add_many(
        db_path,
        [
            make_tx(symbol="600519", qty=100, price=10.0, group="主账户"),
            make_tx(symbol="000001", qty=500, price=2.0, group="打新"),
        ],
    )
    price_cache_dao.upsert(db_path, "600519", 12.0)
    price_cache_dao.upsert(db_path, "000001", 3.0)


def test_by_group_prints_one_block_per_group(use_db, capsys, make_tx):
    _two_groups(use_db, make_tx)

    report_module.report_cmd.callback(by_group=True)

    out = capsys.readouterr().out
    assert "组合：主账户" in out
    assert "组合：打新" in out
    # 两块各自的市值，不是同一个数印两遍。
    assert "1,200.00" in out
    assert "1,500.00" in out


def test_by_group_on_an_empty_db_says_so(use_db, capsys):
    report_module.report_cmd.callback(by_group=True)

    out = capsys.readouterr().out
    assert "暂无组合" in out
    # 没有组合不代表没有绩效：快照是另一条数据源，照印。
    assert "绩效" in out


def test_by_group_takes_the_scope_note_from_the_service(use_db, capsys, monkeypatch, make_tx):
    """句子必须来自服务层，不能写死在渲染层——写死的那份会随口径漂移。"""
    _two_groups(use_db, make_tx)
    monkeypatch.setattr(report_service, "PERFORMANCE_SCOPE_NOTE", "哨兵：绩效是整份组合的")

    report_module.report_cmd.callback(by_group=True)

    assert "哨兵：绩效是整份组合的" in capsys.readouterr().out


def test_without_by_group_the_scope_note_is_not_printed(use_db, capsys, make_tx):
    """不分组时整份报表本来就是一份口径，那句说明只会是噪音。"""
    _two_groups(use_db, make_tx)

    report_module.report_cmd.callback(verbose=False)

    assert report_service.PERFORMANCE_SCOPE_NOTE not in capsys.readouterr().out


def test_group_filters_the_report_to_one_group(use_db, capsys, make_tx):
    _two_groups(use_db, make_tx)

    report_module.report_cmd.callback(group="打新")

    out = capsys.readouterr().out
    assert "000001" in out
    assert "600519" not in out


def test_by_group_with_verbose_shows_each_groups_own_tables(use_db, capsys, make_tx):
    _two_groups(use_db, make_tx)

    report_module.report_cmd.callback(by_group=True, verbose=True)

    out = capsys.readouterr().out
    assert out.count("费用分项") == 2
    assert out.count("资产配置占比") == 2


def test_by_group_and_group_together_is_a_usage_error(use_db):
    """一个说「只看这一组」，一个说「每组都看」，同时给没有合理语义。"""
    with pytest.raises(click.UsageError):
        report_module.report_cmd.callback(by_group=True, group="打新")
