"""没有行情时的展示：显示 `—`，不显示「−100%」。

`current_price` 此前缺省取 `0.0`，于是「还没同步过」被算成了「血亏 100%」——
从未执行 `holdings sync` 就打开 `list` 的用户，看到的是一个不存在的亏损。
"""

from __future__ import annotations

import sys
from datetime import date

import pandas as pd
import pytest

from holdings.cli.main import main
from holdings.cli.renderers.table_renderer import render_summary_line, render_unpriced_hint
from holdings.models.enums import AssetType, MarketType, TradeType
from holdings.models.transaction import Transaction
from holdings.services import portfolio_service
from holdings.storage import price_cache_dao
from holdings.storage.transaction_dao import add_many


def _buy(symbol: str, qty: float, price: float) -> Transaction:
    return Transaction(
        symbol=symbol,
        market=MarketType.A_SHARE,
        asset_type=AssetType.STOCK,
        trade_date=date(2025, 1, 1),
        trade_type=TradeType.BUY,
        quantity=qty,
        price=price,
    )


@pytest.fixture
def mixed(db_path):
    """AAA 有行情（涨了），BBB 没有——「部分有、部分没有」是最常见的情形。"""
    add_many(db_path, [_buy("AAA", 10, 10.0), _buy("BBB", 10, 20.0)])
    price_cache_dao.upsert(db_path, "AAA", 20.0, "CNY", "test")
    return db_path


@pytest.fixture
def use_db(db_path, monkeypatch):
    """把命令内部的 load_config 指向临时库。"""

    class _Cfg:
        database_path = db_path

    monkeypatch.setattr("holdings.utils.config.load_config", lambda *a, **k: _Cfg())
    return db_path


def _run_list(capsys) -> str:
    from holdings.cli.commands import list as list_module

    list_module.list_cmd.callback(sort_key=None, group=None)
    return capsys.readouterr().out


# ------------------------------------------------------------------ 服务层


def test_unpriced_holding_carries_no_numbers(mixed):
    summary = portfolio_service.get_summary(mixed)
    row = summary.holdings_df.set_index("symbol").loc["BBB"]

    assert pd.isna(row["current_price"])
    assert pd.isna(row["market_value"])
    assert pd.isna(row["profit"])
    assert pd.isna(row["profit_rate"])


def test_priced_holding_is_unaffected_by_its_unpriced_neighbour(mixed):
    summary = portfolio_service.get_summary(mixed)
    row = summary.holdings_df.set_index("symbol").loc["AAA"]

    assert row["current_price"] == 20.0
    assert row["market_value"] == pytest.approx(200.0)
    assert row["profit_rate"] == pytest.approx(100.0)


def test_totals_only_cover_the_priced_positions(mixed):
    """汇总的口径是「有行情的标的」，没算进去的部分单独报出来。

    把没行情的按 0 计入市值、却把它的成本计入总成本，会算出一个既不是
    「全体」也不是「部分」的盈亏率。
    """
    summary = portfolio_service.get_summary(mixed)

    assert summary.total_value == pytest.approx(200.0)
    assert summary.total_cost == pytest.approx(100.0), "只算 AAA 的成本"
    assert summary.total_profit == pytest.approx(100.0)
    assert summary.profit_rate == pytest.approx(100.0)
    assert summary.unpriced_symbols == ["BBB"]
    assert summary.unpriced_cost == pytest.approx(200.0)


def test_allocation_ignores_unpriced_positions(mixed):
    """占比表同样只按有行情的市值算，否则会凭空多出一个资产类型。"""
    summary = portfolio_service.get_summary(mixed)

    assert set(summary.allocation) == {"stock"}
    assert summary.allocation["stock"] == pytest.approx(1.0)


def test_everything_unpriced_reports_unknown_not_zero(db_path):
    add_many(db_path, [_buy("AAA", 10, 10.0)])

    summary = portfolio_service.get_summary(db_path)

    assert summary.total_profit is None
    assert summary.profit_rate is None


# ------------------------------------------------------------------ 渲染层


def test_summary_line_shows_dashes_when_nothing_can_be_priced(db_path):
    add_many(db_path, [_buy("AAA", 10, 10.0)])
    summary = portfolio_service.get_summary(db_path)

    line = render_summary_line(summary)

    assert "总市值 —" in line
    assert "总盈亏 —" in line
    assert "累计费用 0.00" in line, "累计费用是账本事实，与有没有行情无关"


def test_hint_names_the_count_and_the_cost(mixed):
    hint = render_unpriced_hint(portfolio_service.get_summary(mixed))

    assert "1 个标的无行情" in hint
    assert "200.00" in hint
    assert "holdings sync" in hint


def test_no_hint_when_everything_is_priced(db_path):
    add_many(db_path, [_buy("AAA", 10, 10.0)])
    price_cache_dao.upsert(db_path, "AAA", 12.0, "CNY", "test")

    assert render_unpriced_hint(portfolio_service.get_summary(db_path)) is None


# ------------------------------------------------------------------ 命令层


def test_list_shows_dashes_and_a_hint_instead_of_a_fake_loss(mixed, use_db, capsys):
    """BACKLOG B-06 的判据：盈亏列显示 `—`，不出现 `-100.00%`，有提示行。"""
    out = _run_list(capsys)

    assert "-100.00%" not in out
    assert "—" in out
    assert "1 个标的无行情" in out


def test_list_recovers_after_sync(db_path, use_db, capsys):
    """同步之后同样的命令恢复正常数字——两个标的都在，都算得出盈亏。"""
    add_many(db_path, [_buy("AAA", 10, 10.0), _buy("BBB", 10, 20.0)])
    price_cache_dao.upsert(db_path, "AAA", 12.0, "CNY", "test")
    price_cache_dao.upsert(db_path, "BBB", 25.0, "CNY", "test")

    out = _run_list(capsys)

    assert "无行情" not in out
    assert "—" not in out
    # 断言汇总行而不是表格单元格：表格在测试环境的窄终端下会被 Rich 截断，
    # 那是 B-07 的事，不该混进这一条里。
    assert "总市值 370.00" in out
    assert "总盈亏 70.00 (23.33%)" in out


def test_sorting_by_a_price_column_puts_unpriced_last(mixed, use_db, capsys):
    """按盈亏率降序时，无行情的不能混进排序结果里。"""
    from holdings.cli.commands import list as list_module

    list_module.list_cmd.callback(sort_key="盈亏率", group=None)
    out = capsys.readouterr().out

    assert out.index("AAA") < out.index("BBB")


def test_sorting_by_a_non_price_column_still_lists_unpriced(mixed, use_db, capsys):
    """按数量这类与价格无关的列排序时，无行情的标的仍要出现在表里。"""
    from holdings.cli.commands import list as list_module

    list_module.list_cmd.callback(sort_key="数量", group=None)
    out = capsys.readouterr().out

    assert "AAA" in out
    assert "BBB" in out


def test_first_run_without_sync_is_not_reported_as_a_loss(tmp_path, monkeypatch, capsys):
    """端到端：装完就跑 list，看到的是提示而不是「血亏」。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text("database_path: holdings.db\n", encoding="utf-8")
    add_many(str(tmp_path / "holdings.db"), [_buy("600519", 100, 1680.5)])
    monkeypatch.setattr(sys, "argv", ["holdings", "list"])

    main()
    out = capsys.readouterr().out

    assert "600519" in out
    assert "-100" not in out
    assert "请先执行 holdings sync" in out
