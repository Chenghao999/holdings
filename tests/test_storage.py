"""storage 层的单元测试（db / 四个 DAO）。"""

import sqlite3
from datetime import date

import pytest

from holdings.models.asset_meta import AssetMeta
from holdings.models.enums import AssetType, MarketType, TradeType
from holdings.models.snapshot import Snapshot
from holdings.storage import (
    asset_meta_dao,
    db,
    price_cache_dao,
    snapshot_dao,
    transaction_dao,
)
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


def test_snapshot_note_round_trips(db_path):
    """备注要真的进库、真的读得回来。

    此前 `snapshot --note` 只在终端回显一句「已记录快照 #2（月度定投第12期）」，
    备注根本没有落库——用户被告知存下了，再去查却什么也没有。
    """
    snap = _snap(1)
    snap.note = "月度定投第12期"
    snapshot_dao.add(db_path, snap)

    assert snapshot_dao.get_all(db_path)[0].note == "月度定投第12期"


def test_snapshot_without_a_note_stores_null_not_an_empty_string(db_path):
    """不传备注存 NULL。「没写备注」与「写了个空备注」在查询与展示上是两回事。"""
    snapshot_dao.add(db_path, _snap(1))

    conn = sqlite3.connect(db_path)
    try:
        raw = conn.execute("SELECT note FROM snapshots").fetchone()[0]
    finally:
        conn.close()

    assert raw is None


def test_connect_migrates_a_database_created_before_note_existed(tmp_path):
    """老库缺少 note 列时，connect() 要把它补上，且不动已有数据。

    `CREATE TABLE IF NOT EXISTS` 对已存在的表完全不生效，所以历史上的新列
    不会自己出现——这一条锁住那段补列逻辑。
    """
    old_db = tmp_path / "old.db"
    conn = sqlite3.connect(old_db)
    try:
        # 用改动前的建表语句造一个「老库」，并塞一行数据
        conn.executescript(
            """
            CREATE TABLE snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_date TEXT NOT NULL UNIQUE,
                total_value REAL NOT NULL,
                cash_balance REAL DEFAULT 0,
                equity_value REAL NOT NULL,
                gold_value REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO snapshots (snapshot_date, total_value, equity_value, gold_value)
            VALUES ('2025-01-01', 1000.0, 800.0, 200.0);
            """
        )
        conn.commit()
    finally:
        conn.close()

    db.connect(str(old_db))  # 迁移在这里发生

    probe = sqlite3.connect(old_db)
    try:
        assert "note" in db._columns(probe, "snapshots")
    finally:
        probe.close()
    got = snapshot_dao.get_all(str(old_db))
    assert got[0].total_value == 1000.0, "补列不该动到已有数据"
    assert got[0].note is None

    # 迁移后的库要能正常写入并读回备注
    snap = _snap(2)
    snap.note = "迁移之后记的"
    snapshot_dao.add(str(old_db), snap)
    assert snapshot_dao.get_all(str(old_db))[1].note == "迁移之后记的"


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


# ---------------------------------------------------------------- asset_meta_dao


def _meta(symbol: str = "518880", **kwargs) -> AssetMeta:
    return AssetMeta(symbol=symbol, **kwargs)


def test_asset_meta_upsert_then_get(db_path):
    asset_meta_dao.upsert(
        db_path, _meta(name="黄金ETF", market="A股", currency="CNY", annual_management_fee=0.5)
    )

    got = asset_meta_dao.get(db_path, "518880")

    assert got.name == "黄金ETF"
    assert got.market == "A股"
    assert got.annual_management_fee == 0.5
    assert got.updated_at is not None


def test_asset_meta_get_returns_none_for_an_unknown_symbol(db_path):
    """没有记录就是没有，不要造一条默认值出来——回落逻辑由调用方决定。"""
    assert asset_meta_dao.get(db_path, "不存在的代码") is None


def test_asset_meta_upsert_twice_updates_in_place(db_path):
    """`symbol` 是主键：重复写入是覆盖，不是插第二条（这是唯一约束的意义）。"""
    asset_meta_dao.upsert(db_path, _meta(name="旧名字", annual_management_fee=0.5))
    asset_meta_dao.upsert(db_path, _meta(name="新名字", annual_management_fee=0.8))

    got = asset_meta_dao.get(db_path, "518880")

    assert got.name == "新名字"
    assert got.annual_management_fee == 0.8
    conn = sqlite3.connect(db_path)
    try:
        count = conn.execute("SELECT COUNT(*) FROM asset_meta").fetchone()[0]
    finally:
        conn.close()
    assert count == 1, "主键冲突应更新而不是新增一行"


def test_asset_meta_upsert_keeps_only_the_given_fields(db_path):
    """只传名称时，费率回到默认值而不是保留上一次的——写的是整条记录。"""
    asset_meta_dao.upsert(db_path, _meta(name="黄金ETF", annual_management_fee=0.5))
    asset_meta_dao.upsert(db_path, _meta(name="黄金ETF"))

    assert asset_meta_dao.get(db_path, "518880").annual_management_fee == 0.0


def test_asset_meta_get_all_is_sorted_by_symbol(db_path):
    asset_meta_dao.upsert(db_path, _meta("600519", name="贵州茅台"))
    asset_meta_dao.upsert(db_path, _meta("518880", name="黄金ETF"))

    assert [m.symbol for m in asset_meta_dao.get_all(db_path)] == ["518880", "600519"]


def test_asset_meta_get_all_on_empty_db(db_path):
    assert asset_meta_dao.get_all(db_path) == []


def test_asset_meta_delete_reports_whether_it_removed_anything(db_path):
    asset_meta_dao.upsert(db_path, _meta(name="黄金ETF"))

    assert asset_meta_dao.delete(db_path, "518880") is True
    assert asset_meta_dao.get(db_path, "518880") is None
    assert asset_meta_dao.delete(db_path, "518880") is False, "重复删除应返回 False"


class _FailingConnection:
    """执行任何语句都抛 sqlite3 异常的假连接。"""

    def execute(self, *_args, **_kwargs):
        raise sqlite3.OperationalError("database is locked")

    def commit(self) -> None:
        raise sqlite3.OperationalError("database is locked")

    def close(self) -> None:
        pass


@pytest.mark.parametrize(
    "call",
    [
        pytest.param(lambda path: asset_meta_dao.get(path, "518880"), id="get"),
        pytest.param(asset_meta_dao.get_all, id="get_all"),
        pytest.param(lambda path: asset_meta_dao.upsert(path, _meta()), id="upsert"),
        pytest.param(lambda path: asset_meta_dao.delete(path, "518880"), id="delete"),
    ],
)
def test_asset_meta_wraps_sqlite_errors(monkeypatch, call):
    """底层 sqlite 异常必须包成 DatabaseError。

    漏出去的话会绕过 `main()` 的退出码映射（`sqlite3.Error` 不是 `HoldingsError`），
    用户看到的是裸 traceback 而不是「错误（4）：…」。
    """
    monkeypatch.setattr(asset_meta_dao, "connect", lambda _path: _FailingConnection())

    with pytest.raises(DatabaseError):
        call("unused.db")
