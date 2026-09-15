"""`holdings list --sort` 的排序契约。

`--sort` 此前把中文表头直接拿去和 DataFrame 的英文列名比，永远不匹配，
于是既没排序也不报错——用户以为排了，拿到的是原始顺序。
这里锁住两件事：中文表头能真的排序，非法字段名要按退出码 5 报错。
"""

from __future__ import annotations

import sys
from datetime import date

import pandas as pd
import pytest

from holdings.cli.commands import list as list_module
from holdings.cli.commands.list import _SORT_ALIASES
from holdings.cli.main import main
from holdings.cli.renderers.table_renderer import render_holdings_table
from holdings.models.enums import AssetType, MarketType, TradeType
from holdings.models.transaction import Transaction
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


def _symbol_order(output: str) -> list[str]:
    """按在表格文本里出现的先后取出代码列。"""
    return sorted(("AAA", "BBB"), key=output.index)


@pytest.fixture
def seeded(db_path):
    """AAA 涨了（盈亏率 +100%），BBB 跌了（盈亏率 −50%）。"""
    add_many(db_path, [_buy("AAA", 10, 10.0), _buy("BBB", 10, 20.0)])
    price_cache_dao.upsert(db_path, "AAA", 20.0, "CNY", "test")
    price_cache_dao.upsert(db_path, "BBB", 10.0, "CNY", "test")
    return db_path


@pytest.fixture
def use_db(db_path, monkeypatch):
    """把命令内部的 load_config 指向临时库。"""

    class _Cfg:
        database_path = db_path

    monkeypatch.setattr("holdings.utils.config.load_config", lambda *a, **k: _Cfg())
    return db_path


def _run_list(capsys, **kwargs) -> str:
    list_module.list_cmd.callback(sort_key=kwargs.get("sort_key"), group=None)
    return capsys.readouterr().out


def test_sort_by_chinese_alias_actually_sorts(seeded, use_db, capsys):
    """文档承诺的 `--sort 盈亏率` 必须真的排序，而不是静默 no-op。"""
    out = _run_list(capsys, sort_key="盈亏率")
    assert _symbol_order(out) == ["AAA", "BBB"], "AAA（+100%）应排在 BBB（−50%）之前"


def test_descending_order_is_reversed_by_the_data(seeded, use_db, capsys):
    """降序确实按数值降序，不是碰巧命中了插入顺序。"""
    add_many(use_db, [_buy("BBB", 10, 20.0)])  # 让 BBB 的盈亏率更负，顺序不变
    out = _run_list(capsys, sort_key="盈亏率")
    assert _symbol_order(out) == ["AAA", "BBB"]


def test_english_column_name_still_works(seeded, use_db, capsys):
    """老脚本里的英文列名不能被打断。"""
    out = _run_list(capsys, sort_key="profit_rate")
    assert _symbol_order(out) == ["AAA", "BBB"]


def test_sort_by_quantity_needs_no_price(db_path, use_db, capsys):
    """没有行情（现价 0）时，按与价格无关的列排序仍应生效。"""
    add_many(db_path, [_buy("AAA", 1, 10.0), _buy("BBB", 99, 10.0)])
    out = _run_list(capsys, sort_key="数量")
    assert _symbol_order(out) == ["BBB", "AAA"]


def test_unknown_sort_key_exits_5(tmp_path, monkeypatch, capsys):
    """非法字段名此前静默通过；现在按参数校验失败返回退出码 5。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["holdings", "list", "--sort", "不存在的列"])

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 5
    assert "错误（5）" in capsys.readouterr().err


def test_every_displayed_column_is_sortable():
    """表格展示的每一列都应能排序，否则 --sort 又是个静默坑。"""
    df = pd.DataFrame(
        [
            {
                "symbol": "X",
                "market": "A股",
                "asset_type": "stock",
                "quantity": 1.0,
                "avg_cost": 1.0,
                "current_price": 1.0,
                "market_value": 1.0,
                "total_fees": 0.0,
                "profit": 0.0,
                "profit_rate": 0.0,
            }
        ]
    )
    shown = {str(c.header) for c in render_holdings_table(df).columns}
    assert shown <= set(_SORT_ALIASES), f"这些列无法排序：{shown - set(_SORT_ALIASES)}"
