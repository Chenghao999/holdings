"""`holdings tui`：终端界面。

界面数据全部来自 `services/`——这正是 B-15 说的「前置条件已具备」：
核心层不许输出、不许依赖终端库、依赖方向合规，都有用例守着。
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from datetime import date

import pytest

from holdings.cli.main import main
from holdings.models.enums import AssetType, MarketType, TradeType
from holdings.models.snapshot import Snapshot
from holdings.models.transaction import Transaction
from holdings.services import portfolio_service
from holdings.storage import price_cache_dao, snapshot_dao
from holdings.storage.transaction_dao import add_many

requires_textual = pytest.mark.skipif(
    importlib.util.find_spec("textual") is None,
    reason="需要 textual（dev extra 里有；本地跑 pip install textual）",
)


def _seed(db_path: str) -> None:
    add_many(
        db_path,
        [
            Transaction(
                symbol="518880",
                market=MarketType.A_SHARE,
                asset_type=AssetType.STOCK,
                trade_date=date(2025, 1, 1),
                trade_type=TradeType.BUY,
                quantity=1000.0,
                price=4.85,
                fee=5.0,
            ),
            Transaction(
                symbol="600519",
                market=MarketType.A_SHARE,
                asset_type=AssetType.STOCK,
                trade_date=date(2025, 1, 1),
                trade_type=TradeType.BUY,
                quantity=100.0,
                price=1680.5,
            ),
        ],
    )
    price_cache_dao.upsert(db_path, "518880", 5.1, "CNY", "test")


# ------------------------------------------------------------------ 缺依赖


def test_without_textual_exits_6_with_an_install_hint(monkeypatch, capsys, tmp_path):
    """Textual 是可选依赖，缺了要按「缺依赖」的契约报，不能漏 ImportError 出去。"""
    for name in ("textual", "textual.app", "textual.widgets", "textual.containers"):
        monkeypatch.setitem(sys.modules, name, None)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["holdings", "tui"])

    try:
        main()
    except SystemExit as exc:
        code = int(exc.code or 0)
    else:
        code = 0

    err = capsys.readouterr().err
    assert code == 6
    assert "错误（6）：" in err
    assert "holdings[tui]" in err, "要给出可执行的安装命令"


# ------------------------------------------------------------------ 界面


@requires_textual
def test_the_app_lists_the_holdings(db_path):
    """BACKLOG B-15 的判据：TUI 能启动、能看持仓。"""
    from textual.widgets import DataTable, Static

    from holdings.tui.app import HoldingsApp

    _seed(db_path)

    async def _run() -> None:
        app = HoldingsApp(db_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            table = app.query_one("#holdings", DataTable)
            assert table.row_count == 2
            summary = app.query_one("#summary", Static)
            assert "总市值" in str(summary.render())

    asyncio.run(_run())


@requires_textual
def test_unpriced_symbols_are_flagged(db_path):
    """没同步过时界面也要说清，而不是显一个不存在的亏损——与 CLI 同口径。"""
    from textual.widgets import Static

    from holdings.tui.app import HoldingsApp

    _seed(db_path)

    async def _run() -> None:
        app = HoldingsApp(db_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert "无行情" in str(app.query_one("#summary", Static).render())

    asyncio.run(_run())


@requires_textual
def test_the_report_tab_shows_the_performance(db_path):
    from textual.widgets import Static

    from holdings.tui.app import HoldingsApp

    _seed(db_path)
    for month, total in ((1, 100.0), (2, 120.0), (3, 90.0), (4, 110.0)):
        snapshot_dao.add(
            db_path,
            Snapshot(
                snapshot_date=date(2025, month, 1),
                total_value=total,
                equity_value=total,
                gold_value=0.0,
            ),
        )

    async def _run() -> None:
        app = HoldingsApp(db_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            report = str(app.query_one("#report", Static).render())
            assert "最大回撤 25.00%" in report
            assert "4 条快照" in report

    asyncio.run(_run())


@requires_textual
def test_refresh_reacts_to_new_data(db_path):
    """`r` 刷新：界面上的数字要跟着库走，而不是停在启动那一刻。"""
    from textual.widgets import DataTable

    from holdings.tui.app import HoldingsApp

    _seed(db_path)

    async def _run() -> None:
        app = HoldingsApp(db_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.query_one("#holdings", DataTable).row_count == 2
            add_many(
                db_path,
                [
                    Transaction(
                        symbol="000001",
                        market=MarketType.A_SHARE,
                        asset_type=AssetType.STOCK,
                        trade_date=date(2025, 1, 1),
                        trade_type=TradeType.BUY,
                        quantity=100.0,
                        price=11.0,
                    )
                ],
            )
            await pilot.press("r")
            await pilot.pause()
            assert app.query_one("#holdings", DataTable).row_count == 3

    asyncio.run(_run())


# ------------------------------------------------------------------ 渲染取值


@requires_textual
def test_the_app_uses_the_shared_column_contract(db_path):
    """表头取自服务层那份列契约，不另写一份——否则两个界面迟早叫法不一致。"""
    from textual.widgets import DataTable

    from holdings.tui.app import _TABLE_COLUMNS, HoldingsApp

    _seed(db_path)
    assert set(_TABLE_COLUMNS) <= set(portfolio_service.HOLDINGS_COLUMNS)

    async def _run() -> None:
        app = HoldingsApp(db_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            table = app.query_one("#holdings", DataTable)
            headers = [str(c.label) for c in table.columns.values()]
            assert headers == [portfolio_service.HOLDINGS_COLUMNS[c] for c in _TABLE_COLUMNS]

    asyncio.run(_run())
