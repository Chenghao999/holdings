"""`holdings meta`：标的名称与年化管理费率的录入。

`asset_meta` 表此前只有建表语句、全项目零引用——SCHEMA.md 写着「完整支持
基金托管费」，却没有任何入口能填。
"""

from __future__ import annotations

import sys

import pytest

from holdings.cli.main import main
from holdings.services import asset_meta_service


@pytest.fixture
def use_db(tmp_path, monkeypatch):
    """一个 config.yaml 指向临时库的项目目录。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text("database_path: holdings.db\n", encoding="utf-8")
    return str(tmp_path / "holdings.db")


def _run(monkeypatch, *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["holdings", "meta", *argv])
    try:
        main()
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


# ------------------------------------------------------------------ 录入


def test_records_name_and_fee_rate(use_db, monkeypatch, capsys):
    """BACKLOG B-01 的判据里的那条命令。"""
    code = _run(monkeypatch, "--symbol", "518880", "--name", "黄金ETF", "--fee-rate", "0.5")

    assert code == 0
    meta = asset_meta_service.get(use_db, "518880")
    assert meta.name == "黄金ETF"
    assert meta.annual_management_fee == 0.5
    assert meta.currency == "CNY", "不给币种时用默认值"


def test_the_output_says_the_rate_is_not_counted(use_db, monkeypatch, capsys):
    """费率不参与成本这件事必须写在用户看得见的地方，不能只写在文档里。"""
    _run(monkeypatch, "--symbol", "518880", "--fee-rate", "0.5")

    out = capsys.readouterr().out
    assert "不参与成本计算" in out


def test_recording_twice_updates_in_place(use_db, monkeypatch):
    _run(monkeypatch, "--symbol", "518880", "--name", "旧名字", "--fee-rate", "0.5")
    _run(monkeypatch, "--symbol", "518880", "--name", "黄金ETF")

    meta = asset_meta_service.get(use_db, "518880")

    assert meta.name == "黄金ETF"
    assert meta.annual_management_fee == 0.5, "没给的字段保留原值，不该被清掉"


# ------------------------------------------------------------------ 查看


def test_without_any_field_it_shows_what_is_recorded(use_db, monkeypatch, capsys):
    """一个字段都不给 = 查一下，而不是写一条空记录把名称与费率清掉。"""
    _run(monkeypatch, "--symbol", "518880", "--name", "黄金ETF", "--fee-rate", "0.5")
    capsys.readouterr()

    _run(monkeypatch, "--symbol", "518880")
    out = capsys.readouterr().out

    assert "黄金ETF" in out
    assert asset_meta_service.get(use_db, "518880").name == "黄金ETF"


def test_a_symbol_without_a_record_says_so(use_db, monkeypatch, capsys):
    _run(monkeypatch, "--symbol", "000001")

    assert "还没有基础信息" in capsys.readouterr().out


# ------------------------------------------------------------------ 删除


def test_remove_deletes_the_record(use_db, monkeypatch, capsys):
    _run(monkeypatch, "--symbol", "518880", "--name", "黄金ETF")
    capsys.readouterr()

    code = _run(monkeypatch, "--symbol", "518880", "--remove")

    assert code == 0
    assert "已删除" in capsys.readouterr().out
    assert asset_meta_service.get(use_db, "518880") is None


def test_removing_something_that_is_not_there_is_not_an_error(use_db, monkeypatch, capsys):
    """重复删除不是错误——目标状态已经达成，报错只会让脚本难写。"""
    code = _run(monkeypatch, "--symbol", "518880", "--remove")

    assert code == 0
    assert "没有基础信息可删" in capsys.readouterr().out


# ------------------------------------------------------------------ 参数


def test_symbol_is_required(use_db, monkeypatch, capsys):
    code = _run(monkeypatch, "--name", "黄金ETF")

    assert code == 5
    assert "错误（5）：" in capsys.readouterr().err


# ------------------------------------------------------------------ 展示


def test_the_rate_changes_nothing_about_the_numbers(use_db, monkeypatch):
    """BACKLOG B-01 的核心判据：录入费率前后，成本价与盈亏**完全一致**。

    这是「费率只作参考展示、不参与成本计算」这句话唯一的客观证明。
    如果哪天有人顺手把费率摊进成本，这条会立刻红。
    """
    from datetime import date

    from holdings.models.enums import AssetType, MarketType, TradeType
    from holdings.models.transaction import Transaction
    from holdings.services import portfolio_service
    from holdings.storage import price_cache_dao, transaction_dao

    transaction_dao.add(
        use_db,
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
    )
    price_cache_dao.upsert(use_db, "518880", 5.1, "CNY", "test")

    before = portfolio_service.get_summary(use_db)

    _run(monkeypatch, "--symbol", "518880", "--name", "黄金ETF", "--fee-rate", "0.5")

    after = portfolio_service.get_summary(use_db)

    assert after.total_cost == before.total_cost
    assert after.total_value == before.total_value
    assert after.total_profit == before.total_profit
    for column in ("avg_cost", "market_value", "profit", "profit_rate"):
        assert after.holdings_df.iloc[0][column] == before.holdings_df.iloc[0][column]


def test_list_shows_the_name(use_db, monkeypatch, capsys):
    from datetime import date

    from holdings.models.enums import AssetType, MarketType, TradeType
    from holdings.models.transaction import Transaction
    from holdings.storage import transaction_dao

    transaction_dao.add(
        use_db,
        Transaction(
            symbol="518880",
            market=MarketType.A_SHARE,
            asset_type=AssetType.STOCK,
            trade_date=date(2025, 1, 1),
            trade_type=TradeType.BUY,
            quantity=1000.0,
            price=4.85,
        ),
    )
    _run(monkeypatch, "--symbol", "518880", "--name", "黄金ETF")

    monkeypatch.setattr(sys, "argv", ["holdings", "list"])
    main()

    assert "黄金ETF" in capsys.readouterr().out


def test_without_a_record_the_name_column_falls_back_to_the_symbol(use_db, monkeypatch):
    """没记过名称就用代码顶上——名称是用来认人的，没有名字时代码就是名字。"""
    from datetime import date

    from holdings.models.enums import AssetType, MarketType, TradeType
    from holdings.models.transaction import Transaction
    from holdings.services import portfolio_service
    from holdings.storage import transaction_dao

    transaction_dao.add(
        use_db,
        Transaction(
            symbol="600519",
            market=MarketType.A_SHARE,
            asset_type=AssetType.STOCK,
            trade_date=date(2025, 1, 1),
            trade_type=TradeType.BUY,
            quantity=100.0,
            price=1680.5,
        ),
    )

    row = portfolio_service.get_summary(use_db).holdings_df.iloc[0]

    assert row["name"] == "600519"


def test_report_shows_the_fee_rate_line_only_when_something_is_recorded(
    use_db, monkeypatch, capsys
):
    from datetime import date

    from holdings.models.enums import AssetType, MarketType, TradeType
    from holdings.models.transaction import Transaction
    from holdings.storage import transaction_dao

    transaction_dao.add(
        use_db,
        Transaction(
            symbol="518880",
            market=MarketType.A_SHARE,
            asset_type=AssetType.STOCK,
            trade_date=date(2025, 1, 1),
            trade_type=TradeType.BUY,
            quantity=1000.0,
            price=4.85,
        ),
    )

    monkeypatch.setattr(sys, "argv", ["holdings", "report"])
    main()
    assert "年化管理费率合计" not in capsys.readouterr().out, "没填过就别印这行"

    _run(monkeypatch, "--symbol", "518880", "--fee-rate", "0.5")
    monkeypatch.setattr(sys, "argv", ["holdings", "report"])
    main()
    out = capsys.readouterr().out

    assert "年化管理费率合计 0.5%" in out
    assert "未计入成本" in out, "旁边就是「累计费用」，不加这句会被读成费用又多了"


def test_the_name_column_is_sortable(use_db, monkeypatch):
    """名称进了表格就该能排序——别名表与表头是同源派生的，这条守着那层连接。"""
    from holdings.cli.commands.list import _SORT_ALIASES

    assert _SORT_ALIASES["名称"] == "name"
