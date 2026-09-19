"""多币种：外币计价的标的不与人民币混加（BACKLOG B-19）。

`PriceResult` 与 `price_cache` 一直记着币种，汇总却完全不看它——持有 AAPL（美元
报价）与 600519（人民币报价）时，总市值是把美元和人民币当同一种货币加出来的数，
而它看起来完全正常。汇率换算留到 v2.0.0，本轮只保证**不混加、如实说明**：

- 非基准货币的标的不进汇总（市值 / 成本 / 盈亏都不加），由提示行报出来；
- 行内账本事实（成本价、累计费用）照常显示，行情派生出来的数字（市值 / 盈亏 /
  盈亏率）显示 `—`——那三个数只有和人民币放一起才有意义，而它们放不到一起；
- 现价照常显示，但带上币种：同一列里混着两种货币而不标注，等于只做了一半。
"""

from __future__ import annotations

import io
from datetime import date

import pandas as pd
import pytest
from rich.console import Console

from holdings.cli.renderers.table_renderer import (
    render_foreign_hint,
    render_holdings_table,
    render_summary_line,
)
from holdings.models.enums import AssetType, MarketType, TradeType
from holdings.models.transaction import Transaction
from holdings.services import portfolio_service
from holdings.storage import price_cache_dao
from holdings.storage.transaction_dao import add_many


def _buy(
    symbol: str,
    qty: float,
    price: float,
    market: MarketType = MarketType.A_SHARE,
    asset_type: AssetType = AssetType.STOCK,
) -> Transaction:
    return Transaction(
        symbol=symbol,
        market=market,
        asset_type=asset_type,
        trade_date=date(2025, 1, 1),
        trade_type=TradeType.BUY,
        quantity=qty,
        price=price,
    )


def _render(df, width: int) -> str:
    console = Console(file=io.StringIO(), width=width, record=True, force_terminal=False)
    console.print(render_holdings_table(df, width=width))
    return console.export_text()


def _run_list(capsys) -> str:
    from holdings.cli.commands import list as list_module

    list_module.list_cmd.callback(sort_key=None, group=None)
    return capsys.readouterr().out


@pytest.fixture
def mixed(db_path):
    """一半人民币一半美元：600519 涨了，AAPL 也涨了（但那个数不加进总额）。"""
    add_many(
        db_path,
        [
            _buy("600519", 100, 10.0),
            _buy("AAPL", 10, 100.0, MarketType.US_STOCK),
        ],
    )
    price_cache_dao.upsert(db_path, "600519", 12.0, "CNY", "test")
    price_cache_dao.upsert(db_path, "AAPL", 200.0, "USD", "test")
    return db_path


@pytest.fixture
def use_db(db_path, monkeypatch):
    """把命令内部的 load_config 指向临时库。"""

    class _Cfg:
        database_path = db_path

    monkeypatch.setattr("holdings.utils.config.load_config", lambda *a, **k: _Cfg())
    return db_path


# ------------------------------------------------------------------ 服务层


def test_all_cny_is_the_baseline(db_path):
    """全是人民币时一切都和改动前一样——这一项只该改变混币种的行为。"""
    add_many(db_path, [_buy("600519", 100, 10.0), _buy("000001", 100, 20.0)])
    price_cache_dao.upsert(db_path, "600519", 12.0, "CNY", "test")
    price_cache_dao.upsert(db_path, "000001", 25.0, "CNY", "test")

    summary = portfolio_service.get_summary(db_path)

    assert summary.total_value == pytest.approx(1200 + 2500)
    assert summary.total_cost == pytest.approx(1000 + 2000)
    assert summary.foreign_holdings == {}
    assert render_foreign_hint(summary) is None


def test_a_foreign_holding_stays_out_of_every_total(mixed):
    """美元标的的市值不进总额——1200 而不是 1200 + 2000。"""
    summary = portfolio_service.get_summary(mixed)

    assert summary.total_value == pytest.approx(1200.0), "只算人民币标的的市值"
    assert summary.total_cost == pytest.approx(1000.0), "成本同理"
    assert summary.total_profit == pytest.approx(200.0)
    assert summary.profit_rate == pytest.approx(20.0)
    assert summary.foreign_holdings == {"AAPL": "USD"}
    assert summary.foreign_cost == pytest.approx(1000.0)
    assert summary.unpriced_symbols == [], "有行情，只是货币不同，不是「没有行情」"


def test_the_foreign_row_keeps_its_price_but_no_derived_numbers(mixed):
    """现价是真的就照实显示；由它推出来的三个数放不进人民币的口径，给 `—`。"""
    row = portfolio_service.get_summary(mixed).holdings_df.set_index("symbol").loc["AAPL"]

    assert row["current_price"] == 200.0
    assert row["currency"] == "USD"
    assert pd.isna(row["market_value"])
    assert pd.isna(row["profit"])
    assert pd.isna(row["profit_rate"])
    assert row["avg_cost"] == pytest.approx(100.0), "账本事实照常显示"
    assert row["total_fees"] == pytest.approx(0.0)


def test_the_cny_row_is_unaffected_by_its_usd_neighbour(mixed):
    row = portfolio_service.get_summary(mixed).holdings_df.set_index("symbol").loc["600519"]

    assert row["currency"] == "CNY"
    assert row["market_value"] == pytest.approx(1200.0)
    assert row["profit"] == pytest.approx(200.0)
    assert row["profit_rate"] == pytest.approx(20.0)


def test_everything_foreign_reports_unknown_not_zero(db_path):
    """一个标的都计不进来时总额是未知，不是 0——0 看着像空仓。"""
    add_many(db_path, [_buy("AAPL", 10, 100.0, MarketType.US_STOCK)])
    price_cache_dao.upsert(db_path, "AAPL", 200.0, "USD", "test")

    summary = portfolio_service.get_summary(db_path)

    assert summary.total_value is None
    assert summary.total_cost is None
    assert summary.total_profit is None
    assert summary.profit_rate is None
    assert summary.foreign_holdings == {"AAPL": "USD"}


def test_allocation_ignores_foreign_positions(db_path):
    """占比表只按人民币市值算，否则会凭空多出一个资产类型。"""
    add_many(
        db_path,
        [
            _buy("518880", 1000, 4.0, asset_type=AssetType.GOLD),
            _buy("AAPL", 10, 100.0, MarketType.US_STOCK),
        ],
    )
    price_cache_dao.upsert(db_path, "518880", 5.0, "CNY", "test")
    price_cache_dao.upsert(db_path, "AAPL", 200.0, "USD", "test")

    summary = portfolio_service.get_summary(db_path)

    assert set(summary.allocation) == {"gold"}, "美元标的的 stock 不该出现在占比里"
    assert summary.allocation["gold"] == pytest.approx(1.0)


# ------------------------------------------------------------------ 渲染层


def test_the_summary_line_shows_dashes_when_nothing_is_countable(db_path):
    add_many(db_path, [_buy("AAPL", 10, 100.0, MarketType.US_STOCK)])
    price_cache_dao.upsert(db_path, "AAPL", 200.0, "USD", "test")

    line = render_summary_line(portfolio_service.get_summary(db_path))

    assert "总市值 —" in line
    assert "总成本 —" in line
    assert "总盈亏 —" in line
    assert "累计费用 0.00" in line, "累计费用是账本事实，与有没有行情无关"


def test_the_hint_names_the_currency_the_count_and_the_cost(mixed):
    hint = render_foreign_hint(portfolio_service.get_summary(mixed))

    assert "1 个标的以美元计价" in hint
    assert "1,000.00" in hint
    assert "未计入上面的汇总" in hint
    assert "不做汇率换算" in hint, "要说清为什么，否则用户会以为程序算漏了"


def test_the_hint_lists_several_currencies(db_path):
    add_many(
        db_path,
        [
            _buy("AAPL", 10, 100.0, MarketType.US_STOCK),
            _buy("00700", 100, 300.0, MarketType.US_STOCK),
            _buy("600519", 100, 10.0),
        ],
    )
    price_cache_dao.upsert(db_path, "AAPL", 200.0, "USD", "test")
    price_cache_dao.upsert(db_path, "00700", 400.0, "HKD", "test")
    price_cache_dao.upsert(db_path, "600519", 12.0, "CNY", "test")

    hint = render_foreign_hint(portfolio_service.get_summary(db_path))

    assert "2 个标的以港币、美元计价" in hint, "按币种代码排序，不按中文码位"


def test_no_hint_when_nothing_is_foreign(db_path):
    add_many(db_path, [_buy("600519", 100, 10.0)])
    price_cache_dao.upsert(db_path, "600519", 12.0, "CNY", "test")

    assert render_foreign_hint(portfolio_service.get_summary(db_path)) is None


def test_the_foreign_price_carries_its_currency(mixed):
    """同一列里混着两种货币而不标注，等于没排除混加。"""
    text = _render(portfolio_service.get_summary(mixed).holdings_df, width=200)

    assert "200.0000 USD" in text
    assert "CNY" not in text, "人民币是默认口径，每行都标只会把这一列撑宽"


def test_an_unpriced_holding_gets_no_currency_tag(db_path):
    """没行情的标的是 `—`，不是 `— CNY`——币种本身也没取到。"""
    add_many(db_path, [_buy("600519", 100, 10.0)])

    text = _render(portfolio_service.get_summary(db_path).holdings_df, width=200)

    assert "CNY" not in text


# ------------------------------------------------------------------ 命令层


def test_list_reports_what_it_left_out(mixed, use_db, capsys):
    """BACKLOG B-19 的判据：总市值不含美元标的，且有明确的提示行。"""
    out = _run_list(capsys)

    assert "总市值 1,200.00" in out
    assert "1 个标的以美元计价" in out
    assert "无行情" not in out, "有行情，只是货币不同，提示语不该混为一谈"
