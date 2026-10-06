"""storage 层的单元测试（db / 四个 DAO）。"""

import sqlite3
from datetime import date, datetime, timezone

import pytest

from holdings.models.asset_meta import AssetMeta
from holdings.models.enums import AssetType, MarketType, TradeType
from holdings.models.snapshot import Snapshot
from holdings.storage import (
    asset_meta_dao,
    db,
    price_cache_dao,
    price_history_dao,
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


def test_connect_migrates_a_database_created_before_import_dedupe(tmp_path, make_tx):
    """老库缺 source / external_id 时，connect() 要补上，且不动已有数据。

    B-29 加这两列时，用户手里的库是改动前建的——`CREATE TABLE IF NOT EXISTS`
    对它完全不生效，不补列的话第一次 `import` 就会撞上「no such column」。
    """
    old_db = tmp_path / "old.db"
    conn = sqlite3.connect(old_db)
    try:
        conn.executescript(
            """
            CREATE TABLE transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_group TEXT DEFAULT '默认',
                symbol TEXT NOT NULL,
                market TEXT NOT NULL,
                asset_type TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                trade_type TEXT NOT NULL,
                quantity REAL NOT NULL,
                price REAL NOT NULL,
                fee REAL DEFAULT 0,
                notes TEXT
            );
            INSERT INTO transactions
                (symbol, market, asset_type, trade_date, trade_type, quantity, price, fee)
            VALUES ('600519', 'A股', 'stock', '2025-01-01', 'BUY', 100, 10, 5.0);
            """
        )
        conn.commit()
    finally:
        conn.close()

    db.connect(str(old_db))  # 迁移在这里发生

    probe = sqlite3.connect(old_db)
    try:
        columns = db._columns(probe, "transactions")
    finally:
        probe.close()
    assert {"source", "external_id"} <= columns

    got = transaction_dao.get_all(str(old_db))
    assert got[0].quantity == 100, "补列不该动到已有数据"
    assert got[0].source is None and got[0].external_id is None, (
        "老数据不知道来源、也没有流水号，是 NULL——补一个猜出来的值会让判重跟着出错"
    )

    # 补列之后要能正常写入并读回这两列
    transaction_dao.add(str(old_db), make_tx(source="csv", external_id="HT-1"))
    assert transaction_dao.get_all(str(old_db))[1].external_id == "HT-1"


def test_connect_migrates_a_database_created_before_instrument_info(tmp_path):
    """老库缺 `asset_meta.asset_type` 时补上，且已有资料不受影响（B-31）。

    补出来是 NULL——**「不知道」而不是「是 stock」**：资产类型猜错会一路走进
    报表，而用户看不出那是猜的。手工填过的名称 / 费率同样一个字都不该动。
    """
    old_db = tmp_path / "old.db"
    conn = sqlite3.connect(old_db)
    try:
        conn.executescript(
            """
            CREATE TABLE asset_meta (
                symbol TEXT PRIMARY KEY,
                name TEXT,
                market TEXT,
                currency TEXT DEFAULT 'CNY',
                annual_management_fee REAL DEFAULT 0,
                updated_at TEXT
            );
            INSERT INTO asset_meta
                (symbol, name, market, currency, annual_management_fee)
            VALUES ('600519', '贵州茅台', 'A股', 'CNY', 0.5);
            """
        )
        conn.commit()
    finally:
        conn.close()

    db.connect(str(old_db))  # 迁移在这里发生

    probe = sqlite3.connect(old_db)
    try:
        assert "asset_type" in db._columns(probe, "asset_meta")
    finally:
        probe.close()

    got = asset_meta_dao.get(str(old_db), "600519")
    assert (got.name, got.market, got.annual_management_fee) == ("贵州茅台", "A股", 0.5)
    assert got.asset_type is None, "老数据不知道资产类型，补一个猜出来的值会跟着误导报表"

    # 补列之后要能正常写入并读回
    asset_meta_dao.upsert(
        str(old_db), AssetMeta(symbol="600519", name="贵州茅台", asset_type="etf")
    )
    assert asset_meta_dao.get(str(old_db), "600519").asset_type is AssetType.ETF


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


# --------------------------------------------------------------- 缓存新鲜度


def test_timestamp_is_fresh_compares_against_utc_not_local_time():
    """SQLite 的 `CURRENT_TIMESTAMP` 存的是 UTC，算年龄就得跟 UTC 比。

    用本地时间在东八区会把「刚刚写入」算成 8 小时前，于是缓存永远不新鲜、
    每次都重新联网——而一切看起来都正常。这条用例专门钉住这个方向。
    """
    just_now_utc = datetime.now(timezone.utc).replace(tzinfo=None).isoformat(sep=" ")

    assert db.timestamp_is_fresh(just_now_utc, ttl_seconds=300) is True
    assert db.timestamp_is_fresh(just_now_utc, ttl_seconds=0) is False, "ttl 为 0 就是永不新鲜"


@pytest.mark.parametrize("value", [None, "", "不是时间"])
def test_timestamp_is_fresh_is_false_for_a_missing_or_broken_value(value):
    """读不出时间就当过期——重新取一次的代价远小于用一份不知道多旧的资料。"""
    assert db.timestamp_is_fresh(value, ttl_seconds=86400) is False


def test_asset_meta_is_fresh_needs_a_name(db_path):
    """只有费率、没有名字的行不算「有新资料」。

    手工 `holdings meta --fee` 建出来的行也在库里，若把它当缓存命中，
    这条代码的名称就永远取不回来了。
    """
    asset_meta_dao.upsert(db_path, _meta(annual_management_fee=0.5))

    assert asset_meta_dao.is_fresh(db_path, "518880", ttl_seconds=86400) is False

    asset_meta_dao.upsert(db_path, _meta(name="黄金ETF"))
    assert asset_meta_dao.is_fresh(db_path, "518880", ttl_seconds=86400) is True


def test_asset_meta_is_fresh_is_false_for_an_unknown_symbol(db_path):
    assert asset_meta_dao.is_fresh(db_path, "从没记过", ttl_seconds=86400) is False


class _FailingConnection:
    """执行任何语句都抛 sqlite3 异常的假连接。"""

    def execute(self, *_args, **_kwargs):
        raise sqlite3.OperationalError("database is locked")

    def executemany(self, *_args, **_kwargs):
        # `price_history_dao.upsert_many` 走的是批量接口；假连接得把这一条也接住，
        # 否则报出来的是 AttributeError 而不是用例要验的那个 DatabaseError。
        raise sqlite3.OperationalError("database is locked")

    def commit(self) -> None:
        raise sqlite3.OperationalError("database is locked")

    def rollback(self) -> None:
        # 回滚不抛：要验的是「底层出错 → DatabaseError」，回滚本身失败是另一件事
        # （`add_many` 也有同样的形状），混在一起会让这条用例验不准。
        pass

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


# ------------------------------------------------------- transaction_dao: 组合（B-21）


def test_connect_creates_the_group_index(db_path):
    """`portfolio_group` 上要有索引：列出组合与按组合筛选都打这一列。

    老库同样会补上——`init_schema` 每次 connect 都跑 `executescript(SCHEMA_SQL)`，
    而语句是 `CREATE INDEX IF NOT EXISTS`。
    """
    conn = connect(db_path)
    try:
        names = {
            r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
        }
    finally:
        conn.close()

    assert "idx_trans_group" in names


def test_list_groups_returns_distinct_names_in_order(db_path, make_tx):
    transaction_dao.add(db_path, make_tx(symbol="A", group="打新"))
    transaction_dao.add(db_path, make_tx(symbol="B", group="默认"))
    transaction_dao.add(db_path, make_tx(symbol="C", group="打新"))

    assert transaction_dao.list_groups(db_path) == ["打新", "默认"]


def test_list_groups_on_empty_db_is_empty(db_path):
    assert transaction_dao.list_groups(db_path) == []


def test_list_groups_skips_null_groups(db_path, make_tx):
    """NULL 不是组合名。

    `portfolio_group` 只有 `DEFAULT '默认'` 而没有 NOT NULL，老库或手工插入的
    行可能是 NULL。把它当名字返回出去，调用方拿它筛交易会得到一条空结果，
    看起来像有个叫 None 的空组合。
    """
    transaction_dao.add(db_path, make_tx(group="打新"))
    conn = connect(db_path)
    try:
        conn.execute(
            "INSERT INTO transactions (portfolio_group, symbol, market, asset_type, "
            "trade_date, trade_type, quantity, price) "
            "VALUES (NULL, '600519', 'A股', 'stock', '2025-01-01', 'BUY', 1, 1)"
        )
        conn.commit()
    finally:
        conn.close()

    assert transaction_dao.list_groups(db_path) == ["打新"]


def test_move_group_rewrites_all_matching_rows_and_returns_count(db_path, make_tx):
    transaction_dao.add(db_path, make_tx(symbol="A", group="打新"))
    transaction_dao.add(db_path, make_tx(symbol="B", group="打新"))
    transaction_dao.add(db_path, make_tx(symbol="C", group="默认"))

    moved = transaction_dao.move_group(db_path, "打新", "主账户")

    assert moved == 2
    assert transaction_dao.list_groups(db_path) == ["主账户", "默认"]
    assert [t.symbol for t in transaction_dao.get_all(db_path, group="主账户")] == ["A", "B"]
    assert transaction_dao.get_all(db_path, group="打新") == []


def test_move_group_returns_zero_for_an_unknown_source(db_path, make_tx):
    transaction_dao.add(db_path, make_tx(group="默认"))

    assert transaction_dao.move_group(db_path, "不存在的组合", "别的") == 0
    # 没匹配到行也不该凭空建一个组合出来。
    assert transaction_dao.list_groups(db_path) == ["默认"]


@pytest.mark.parametrize(
    "call",
    [
        pytest.param(transaction_dao.list_groups, id="list_groups"),
        pytest.param(lambda path: transaction_dao.move_group(path, "a", "b"), id="move_group"),
    ],
)
def test_group_dao_wraps_sqlite_errors(monkeypatch, call):
    """底层 sqlite 异常必须包成 DatabaseError。

    漏出去的话会绕过 `main()` 的退出码映射（`sqlite3.Error` 不是 `HoldingsError`），
    用户看到的是裸 traceback 而不是「错误（4）：…」。
    """
    monkeypatch.setattr(transaction_dao, "connect", lambda _path: _FailingConnection())

    with pytest.raises(DatabaseError):
        call("unused.db")


# ------------------------------------------------- price_history_dao（B-39）


def _days(*specs: tuple[str, float]) -> list[tuple[date, float]]:
    return [(date.fromisoformat(day), close) for day, close in specs]


def test_price_history_round_trips_a_range(db_path):
    """写入后按区间读回来，升序、两端都是闭区间。"""
    price_history_dao.upsert_many(
        db_path,
        "000300",
        _days(("2024-01-02", 3000.0), ("2024-01-03", 3060.0), ("2024-02-01", 3200.0)),
        "akshare",
    )

    got = price_history_dao.get_range(db_path, "000300", date(2024, 1, 1), date(2024, 1, 31))

    assert got == _days(("2024-01-02", 3000.0), ("2024-01-03", 3060.0))


def test_price_history_upsert_merges_instead_of_wiping(db_path):
    """同一代码重复取数是**合并写**：已经有的日子留着，新的补进来，改的覆盖掉。

    清空重写在这里是错的：用户把 `--start` 往前挪时新取回来的只是一部分，
    清空会把上次那段抹掉。
    """
    price_history_dao.upsert_many(db_path, "000300", _days(("2024-01-02", 3000.0)), "akshare")
    price_history_dao.upsert_many(
        db_path,
        "000300",
        _days(("2024-01-02", 3001.0), ("2024-01-03", 3060.0)),
        "akshare",
    )

    got = price_history_dao.get_range(db_path, "000300", date(2024, 1, 1), date(2024, 1, 31))

    assert got == _days(("2024-01-02", 3001.0), ("2024-01-03", 3060.0))


def test_price_history_keeps_symbols_apart(db_path):
    price_history_dao.upsert_many(db_path, "000300", _days(("2024-01-02", 3000.0)), "akshare")
    price_history_dao.upsert_many(db_path, "000905", _days(("2024-01-02", 5000.0)), "akshare")

    got = price_history_dao.get_range(db_path, "000905", date(2024, 1, 1), date(2024, 1, 31))

    assert got == _days(("2024-01-02", 5000.0))


def test_price_history_upsert_many_does_nothing_for_an_empty_list(db_path):
    assert price_history_dao.upsert_many(db_path, "000300", [], "akshare") == 0


def test_price_history_range_of_an_unknown_symbol_is_empty(db_path):
    assert (
        price_history_dao.get_range(db_path, "从没取过", date(2024, 1, 1), date(2024, 1, 31)) == []
    )


def test_price_history_is_fresh_is_false_without_any_row(db_path):
    """一条历史都没有过 —— 不新鲜，去取。"""
    assert (
        price_history_dao.is_fresh(db_path, "000300", date(2024, 1, 1), date(2024, 1, 31), 86400)
        is False
    )


def test_price_history_is_fresh_is_false_when_the_range_is_not_covered(db_path):
    """**这一条防的是静默少一段**：用户把 `--start` 往前挪，缓存里没有那一段。

    若只判「有没有行」，就会拿一段缺了开头的序列去算收益——数字看着完全正常。
    """
    price_history_dao.upsert_many(
        db_path, "000300", _days(("2024-06-03", 3000.0), ("2024-06-28", 3100.0)), "akshare"
    )

    # 缓存从 6 月起，却问 1 月起的那一段 → 盖不住。
    assert (
        price_history_dao.is_fresh(db_path, "000300", date(2024, 1, 1), date(2024, 6, 28), 86400)
        is False
    )
    # 问的是缓存盖得住的那一段 → 命中。
    assert (
        price_history_dao.is_fresh(db_path, "000300", date(2024, 6, 3), date(2024, 6, 28), 86400)
        is True
    )


def test_price_history_is_fresh_is_false_when_the_cache_is_too_old(db_path):
    """行都在、区间也盖得住，但最新一次取数已经是太久以前 → 不新鲜。

    `updated_at` 直接写一个明确的旧时间，不走 SQLite 的 `CURRENT_TIMESTAMP`
    （那永远是"现在"，测不出过期）。
    """
    price_history_dao.upsert_many(
        db_path, "000300", _days(("2024-01-02", 3000.0), ("2024-01-31", 3100.0)), "akshare"
    )
    conn = connect(db_path)
    try:
        conn.execute("UPDATE price_history SET updated_at = '2020-01-01 00:00:00'")
        conn.commit()
    finally:
        conn.close()

    assert (
        price_history_dao.is_fresh(db_path, "000300", date(2024, 1, 1), date(2024, 1, 31), 86400)
        is False
    )


def test_price_history_is_fresh_tolerates_non_trading_days_at_the_edges(db_path):
    """区间边缘落在周末 / 长假时，那几天本来就不会有行，不该判成没盖住。

    不放宽的话，一次周末发起的查询会永远命不中，每次跑都白打一遍网络——
    缓存形同虚设，而看起来一切正常。
    """
    # 只有工作日有行：2024-01-05 是周五，2024-01-08 是周一。
    price_history_dao.upsert_many(
        db_path, "000300", _days(("2024-01-05", 3000.0), ("2024-01-08", 3060.0)), "akshare"
    )

    # 问的区间两端都落在周末（01-06 周六、01-07 周日）。
    assert (
        price_history_dao.is_fresh(db_path, "000300", date(2024, 1, 6), date(2024, 1, 7), 86400)
        is True
    )


@pytest.mark.parametrize(
    "call",
    [
        pytest.param(
            lambda path: price_history_dao.get_range(
                path, "000300", date(2024, 1, 1), date(2024, 1, 31)
            ),
            id="get_range",
        ),
        pytest.param(
            lambda path: price_history_dao.upsert_many(
                path, "000300", _days(("2024-01-02", 3000.0)), "akshare"
            ),
            id="upsert_many",
        ),
        pytest.param(
            lambda path: price_history_dao.is_fresh(
                path, "000300", date(2024, 1, 1), date(2024, 1, 31), 86400
            ),
            id="is_fresh",
        ),
    ],
)
def test_price_history_dao_wraps_sqlite_errors(monkeypatch, call):
    """底层 sqlite 异常必须包成 DatabaseError，否则会绕过 `main()` 的退出码映射。"""
    monkeypatch.setattr(price_history_dao, "connect", lambda _path: _FailingConnection())

    with pytest.raises(DatabaseError):
        call("unused.db")
