"""窄终端下的持仓表：代码列必须完整可辨。

持仓表有 10 列，80 列终端放不下，Rich 于是平均截断每一列——代码列只剩
`6005…`，用户从表里认不出自己持的是什么。这是默认终端的默认行为，
不是边缘情况。
"""

from __future__ import annotations

import io
from datetime import date

import pandas as pd
import pytest
from rich.console import Console

from holdings.cli.renderers.table_renderer import (
    COMPACT_COLUMNS,
    COMPACT_WIDTH_THRESHOLD,
    render_holdings_table,
)
from holdings.models.enums import AssetType, MarketType, TradeType
from holdings.models.transaction import Transaction
from holdings.services.portfolio_service import HOLDINGS_COLUMNS
from holdings.storage import price_cache_dao
from holdings.storage.transaction_dao import add_many

NARROW = 80
WIDE = 120


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


def _summary(db_path):
    from holdings.services import portfolio_service

    add_many(
        db_path,
        [
            _buy("600519", 100, 1680.5),
            _buy("518880", 1000, 4.85),
            _buy("000001", 500, 11.2),
        ],
    )
    for symbol, price in (("600519", 1750.0), ("518880", 5.1), ("000001", 10.8)):
        price_cache_dao.upsert(db_path, symbol, price, "CNY", "test")
    return portfolio_service.get_summary(db_path)


def _render(df, width: int) -> str:
    console = Console(file=io.StringIO(), width=width, record=True, force_terminal=False)
    console.print(render_holdings_table(df, width=width))
    return console.export_text()


def _headers(df, width: int | None) -> list[str]:
    """表头列表。「盈亏」是「盈亏率」的子串，直接对渲染文本做子串判断会误判。"""
    table = render_holdings_table(df, width=width) if width else render_holdings_table(df)
    return [str(c.header) for c in table.columns]


# ------------------------------------------------------------------ 窄终端


def test_symbol_is_fully_visible_at_80_columns(db_path):
    """BACKLOG B-07 的判据：`600519` 而不是 `6005…`。"""
    text = _render(_summary(db_path).holdings_df, NARROW)

    for symbol in ("600519", "518880", "000001"):
        assert symbol in text, f"{symbol} 在 80 列下被截断了"
    assert "…" not in text, "窄终端下不该出现任何省略号"


def test_no_line_exceeds_the_terminal_width(db_path):
    """行宽不能超出终端，否则会被折行或横向滚动，比截断更难读。"""
    text = _render(_summary(db_path).holdings_df, NARROW)

    assert max(len(line) for line in text.splitlines()) <= NARROW


def test_narrow_terminal_shows_exactly_the_four_compact_columns(db_path):
    """少显示几列是有意的取舍：10 列在 80 列里只能每列都看不清。"""
    headers = _headers(_summary(db_path).holdings_df, NARROW)

    assert headers == [HOLDINGS_COLUMNS[c] for c in COMPACT_COLUMNS]


# ------------------------------------------------------------------ 宽终端


def test_wide_terminal_still_shows_every_column(db_path):
    """宽终端不被牵连：列数与改动前一致，不多不少。"""
    df = _summary(db_path).holdings_df
    text = _render(df, WIDE)

    assert _headers(df, WIDE) == list(HOLDINGS_COLUMNS.values())
    assert "…" not in text
    assert max(len(line) for line in text.splitlines()) <= WIDE


def test_the_threshold_is_between_the_two_widths_we_test():
    """两个用例的宽度必须真的落在阈值两侧，否则这组测试什么也没锁住。"""
    assert NARROW < COMPACT_WIDTH_THRESHOLD <= WIDE


def test_unknown_width_falls_back_to_the_full_table():
    """不传宽度时保持原样：调用方（含既有测试）不该被迫关心终端宽度。"""
    df = pd.DataFrame([{"symbol": "600519", "quantity": 1.0}])

    assert _headers(df, None) == list(HOLDINGS_COLUMNS.values())


def test_compact_columns_are_a_subset_of_the_full_table():
    """简表只能从全表里挑列，不能出现全表没有的列。"""
    assert set(COMPACT_COLUMNS) <= set(HOLDINGS_COLUMNS)


@pytest.mark.parametrize("width", [60, 80, 99])
def test_every_narrow_width_keeps_the_symbol_intact(db_path, width):
    text = _render(_summary(db_path).holdings_df, width)

    assert "600519" in text
    assert max(len(line) for line in text.splitlines()) <= width
