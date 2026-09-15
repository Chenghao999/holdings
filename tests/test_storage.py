"""storage 层（db / transaction_dao / snapshot_dao / price_cache_dao）的单元测试。"""

from datetime import date

import pytest

from holdings.models.enums import AssetType, MarketType, TradeType
from holdings.models.snapshot import Snapshot
from holdings.storage import price_cache_dao, snapshot_dao, transaction_dao
from holdings.storage.db import DatabaseError, connect

# --------------------------------------------------------------------------- db


def test_connect_creates_schema_and_parent_dirs(tmp_path):
    """connect 应自动建父目录并建出全部表。"""
    path = tmp_path / "nested" / "sub" / "holdings.db"
    conn = connect(str(path))
    try:
        names = {
            r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    finally:
        conn.close()

    assert {"transactions", "snapshots", "asset_meta", "price_cache"} <= names
    assert path.exists()


def test_connect_enables_row_factory(db_path):
    """查询结果应支持按列名取值。"""
    conn = connect(db_path)
    try:
        conn.execute(
            "INSERT INTO transactions (symbol, market, asset_type, trade_date, "
            "trade_type, quantity, price) VALUES ('600519', 'A股', 'stock', "
            "'2025-01-01', 'BUY', 100, 10)"
        )
        conn.commit()
        row = conn.execute("SELECT symbol FROM transactions").fetchone()
    finally:
        conn.close()

    assert row["symbol"] == "600519"


# ---------------------------------------------------------------- transaction_dao


def test_add_returns_incrementing_id(db_path, make_tx):
    first = transaction_dao.add(db_path, make_tx())
    second = transaction_dao.add(db_path, make_tx())

    assert first == 1
    assert second == 2


def test_add_then_get_roundtrips_all_fields(db_path, make_tx):
    """写入再读出，枚举、日期、费用等字段不应失真。"""
    tx_id = transaction_dao.add(
        db_path,
        make_tx(
            symbol="AAPL",
            market=MarketType.US_STOCK,
            asset_type=AssetType.ETF,
            trade_date=date(2025, 3, 17),
            trade_type="SELL",
            qty=40,
            price=12.5,
            fee=1.75,
            group="美股组合",
            notes="减仓",
        ),
    )

    got = transaction_dao.get(db_path, tx_id)

    assert got is not None
    assert got.id == tx_id
    assert got.symbol == "AAPL"
    assert got.market is MarketType.US_STOCK
    assert got.asset_type is AssetType.ETF
    assert got.trade_type is TradeType.SELL
    assert got.trade_date == date(2025, 3, 17)
    assert got.quantity == 40
    assert got.price == 12.5
    assert got.fee == 1.75
    assert got.portfolio_group == "美股组合"
    assert got.notes == "减仓"


def test_get_missing_id_returns_none(db_path):
    assert transaction_dao.get(db_path, 999) is None


def test_get_all_orders_by_date_then_id(db_path, make_tx):
    """后插入但日期更早的记录应排在前面。"""
    late = transaction_dao.add(db_path, make_tx(trade_date=date(2025, 5, 1)))
    early = transaction_dao.add(db_path, make_tx(trade_date=date(2025, 1, 1)))

    ids = [t.id for t in transaction_dao.get_all(db_path)]

    assert ids == [early, late]


def test_get_all_same_date_falls_back_to_id(db_path, make_tx):
    """同日多笔按写入顺序返回。"""
    same_day = date(2025, 1, 1)
    a = transaction_dao.add(db_path, make_tx(trade_date=same_day))
    b = transaction_dao.add(db_path, make_tx(trade_date=same_day))

    assert [t.id for t in transaction_dao.get_all(db_path)] == [a, b]


def test_get_all_filters_by_group(db_path, make_tx):
    transaction_dao.add(db_path, make_tx(symbol="A", group="默认"))
    transaction_dao.add(db_path, make_tx(symbol="B", group="打新"))

    assert [t.symbol for t in transaction_dao.get_all(db_path, group="打新")] == ["B"]
    assert len(transaction_dao.get_all(db_path)) == 2


def test_get_all_on_empty_db_returns_empty_list(db_path):
    assert transaction_dao.get_all(db_path) == []


def test_remove_deletes_and_reports(db_path, make_tx):
    tx_id = transaction_dao.add(db_path, make_tx())

    assert transaction_dao.remove(db_path, tx_id) is True
    assert transaction_dao.get(db_path, tx_id) is None
    assert transaction_dao.remove(db_path, tx_id) is False


def test_symbols_are_distinct(db_path, make_tx):
    transaction_dao.add(db_path, make_tx(symbol="600519"))
    transaction_dao.add(db_path, make_tx(symbol="600519"))
    transaction_dao.add(db_path, make_tx(symbol="AAPL"))

    assert sorted(transaction_dao.symbols(db_path)) == ["600519", "AAPL"]


# ------------------------------------------------------------------- snapshot_dao


def _snap(day: int, total: float = 1000.0) -> Snapshot:
    return Snapshot(
        snapshot_date=date(2025, 1, day),
        total_value=total,
        equity_value=total * 0.8,
        gold_value=total * 0.2,
        cash_balance=0.0,
    )


def test_snapshot_add_then_get_all(db_path):
    snapshot_dao.add(db_path, _snap(1, 1000.0))
    snapshot_dao.add(db_path, _snap(2, 1100.0))

    got = snapshot_dao.get_all(db_path)

    assert [s.snapshot_date for s in got] == [date(2025, 1, 1), date(2025, 1, 2)]
    assert got[1].total_value == 1100.0
    assert round(got[0].equity_value, 4) == 800.0
    assert got[0].created_at is not None


def test_snapshot_get_all_ordered_by_date_not_insert_order(db_path):
    snapshot_dao.add(db_path, _snap(5))
    snapshot_dao.add(db_path, _snap(2))

    assert [s.snapshot_date.day for s in snapshot_dao.get_all(db_path)] == [2, 5]


def test_snapshot_duplicate_date_raises(db_path):
    """同一天只能有一份快照，重复写入应转成 DatabaseError。"""
    snapshot_dao.add(db_path, _snap(1))

    with pytest.raises(DatabaseError, match="该日期快照已存在"):
        snapshot_dao.add(db_path, _snap(1))


def test_snapshot_get_all_on_empty_db(db_path):
    assert snapshot_dao.get_all(db_path) == []


# --------------------------------------------------------------- price_cache_dao


def test_price_cache_upsert_then_get(db_path):
    price_cache_dao.upsert(db_path, "600519", 1680.5, currency="CNY", source="akshare")

    got = price_cache_dao.get(db_path, "600519")

    assert got is not None
    assert got.symbol == "600519"
    assert got.price == 1680.5
    assert got.currency == "CNY"
    assert got.source == "akshare"
    assert got.update_time


def test_price_cache_upsert_overwrites_existing(db_path):
    """同一标的二次写入应覆盖，而不是插出两行。"""
    price_cache_dao.upsert(db_path, "600519", 10.0, source="old")
    price_cache_dao.upsert(db_path, "600519", 20.0, source="new")

    got = price_cache_dao.get(db_path, "600519")

    assert got.price == 20.0
    assert got.source == "new"

    conn = connect(db_path)
    try:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM price_cache WHERE symbol = '600519'"
        ).fetchone()["c"]
    finally:
        conn.close()

    assert count == 1


def test_price_cache_get_missing_returns_none(db_path):
    assert price_cache_dao.get(db_path, "NOPE") is None


def test_price_cache_upsert_defaults(db_path):
    price_cache_dao.upsert(db_path, "AAPL", 190.0)

    got = price_cache_dao.get(db_path, "AAPL")

    assert got.currency == "CNY"
    assert got.source == ""


def test_is_fresh_true_for_just_written_entry(db_path):
    price_cache_dao.upsert(db_path, "600519", 10.0)

    assert price_cache_dao.is_fresh(db_path, "600519", 300) is True


def test_is_fresh_false_for_missing_symbol(db_path):
    assert price_cache_dao.is_fresh(db_path, "NOPE", 300) is False


def test_is_fresh_false_for_stale_entry(db_path):
    """把 update_time 改到很久以前，应判定为过期。"""
    price_cache_dao.upsert(db_path, "600519", 10.0)
    conn = connect(db_path)
    try:
        conn.execute(
            "UPDATE price_cache SET update_time = ? WHERE symbol = ?",
            ("2020-01-01 00:00:00", "600519"),
        )
        conn.commit()
    finally:
        conn.close()

    assert price_cache_dao.is_fresh(db_path, "600519", 300) is False


def test_is_fresh_false_for_unparsable_timestamp(db_path):
    """脏数据不应让 is_fresh 抛异常。"""
    price_cache_dao.upsert(db_path, "600519", 10.0)
    conn = connect(db_path)
    try:
        conn.execute(
            "UPDATE price_cache SET update_time = ? WHERE symbol = ?",
            ("不是时间", "600519"),
        )
        conn.commit()
    finally:
        conn.close()

    assert price_cache_dao.is_fresh(db_path, "600519", 300) is False
