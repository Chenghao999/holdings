"""`holdings export`：账本 / 持仓表 / 快照的出口（BACKLOG B-37）。

此前只有半个回路——`holdings import` 能读三种格式，却没有任何东西能写出来，
报税、迁移、备份三个场景全堵着。

这里最要紧的一条是**往返**：账本导出去还能导回来。它同时钉住了两件容易走样
的事——表头得是 `import` 认的那一份，金额不能被「四舍五入得好看一点」。
"""

from __future__ import annotations

import codecs
import csv
import json
import sys
from datetime import date

import pytest

from holdings.cli.main import main
from holdings.data import brokers
from holdings.data.brokers.canonical import CanonicalCsv
from holdings.models.enums import MarketType
from holdings.models.snapshot import Snapshot
from holdings.services import export_service, portfolio_service
from holdings.storage import price_cache_dao, snapshot_dao, transaction_dao


@pytest.fixture
def seeded(db_path, make_tx):
    """一个两组的账本 + 一条快照，且**只有一个标的取到行情**。

    那个没有行情的标的（AAPL）是故意的：它那几格的市值与盈亏算不出来，
    正好用来验「缺失写成空/null，而不是 `nan`」。
    """
    transaction_dao.add_many(
        db_path,
        [
            make_tx(
                symbol="600519",
                qty=100.0,
                price=10.0,
                fee=5.0,
                notes="第一笔",
                trade_date=date(2025, 1, 1),
                source="demo-a",
                external_id="A-1",
            ),
            make_tx(
                symbol="AAPL",
                market=MarketType.US_STOCK,
                qty=10.0,
                price=200.0,
                group="美股账户",
                trade_date=date(2025, 2, 1),
            ),
            make_tx(
                symbol="600519",
                trade_type="SELL",
                qty=40.0,
                price=12.0,
                fee=1.0,
                trade_date=date(2025, 3, 1),
            ),
        ],
    )
    price_cache_dao.upsert(db_path, "600519", 11.0, "CNY", "test")
    snapshot_dao.add(
        db_path,
        Snapshot(
            snapshot_date=date(2025, 1, 31),
            total_value=1000.0,
            equity_value=900.0,
            gold_value=100.0,
            note="一月",
        ),
    )
    return db_path


def _point_at(monkeypatch, db_path: str) -> str:
    """把命令内部的 `load_config` 指向某个库。

    与 `test_chart_cmd.py` 同一个写法：命令里的 `cfg = load_config()` 是在函数
    体里调的，所以打得中。给的是**真的 `Config`** 而不是一个只有两三个属性的
    替身——往返要跑 `holdings import` 那条完整链路，它读的配置项比导出多。
    """
    from holdings.utils.config import Config

    cfg = Config()
    cfg.set("database_path", db_path)
    monkeypatch.setattr("holdings.utils.config.load_config", lambda *a, **k: cfg)
    return db_path


def _run(monkeypatch, sub: str, *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["holdings", sub, *argv])
    try:
        main()
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


def _export(monkeypatch, tmp_path, what: str, fmt: str):
    """跑一次导出，返回产物路径。"""
    out_file = tmp_path / f"{what}.{fmt}"
    code = _run(monkeypatch, "export", "--what", what, "--format", fmt, "--out", str(out_file))
    assert code == 0, f"{what}.{fmt} 导出失败，退出码 {code}"
    return out_file


# ------------------------------------------------------------------ 账本：表头派生


def test_the_ledger_header_is_derived_from_canonical(seeded, monkeypatch):
    """表头是**派生**的，不是照着 `canonical.py` 另抄一份。

    把 canonical 里某一列的写法换掉，导出的表头必须跟着换。抄一份的写法在这条
    用例下纹丝不动——而它正是「canonical 加了列、导出的文件从此少一列」的源头。
    """
    monkeypatch.setitem(CanonicalCsv.columns, "symbol", ("证券代码",))

    columns = export_service.ledger(seeded).columns

    assert "证券代码" in columns
    assert "symbol" not in columns, "表头是抄来的一份，不跟着 canonical 走"


def test_every_canonical_column_has_a_value_to_write(make_tx):
    """canonical 里的每一列，导出时都有值可填。

    少填一列是**静默**的：文件照样写出来、退出码照样 0，要到「导回来发现数据
    缺了」才会被发现。所以宁可在这一层当场红。
    """
    fields = set(CanonicalCsv.columns)
    values = set(export_service._ledger_values(make_tx()))

    assert fields <= values, f"这几列在导出时没有值：{'、'.join(sorted(fields - values))}"


def test_a_new_canonical_column_cannot_be_dropped_silently(seeded, monkeypatch):
    """真加了列又没填值，是当场炸，不是少写一列悄悄放过。"""
    monkeypatch.setitem(CanonicalCsv.columns, "broker_note", ("broker_note",))

    with pytest.raises(KeyError, match="broker_note"):
        export_service.ledger(seeded)


# ------------------------------------------------------------------ 账本：往返


def _round_trip(monkeypatch, tmp_path, db_path, capsys) -> str:
    """把 `db_path` 的账本导出来，再导进一个**空库**，返回那个空库的路径。"""
    _point_at(monkeypatch, db_path)
    ledger = tmp_path / "ledger.csv"
    assert _run(monkeypatch, "export", "--out", str(ledger)) == 0
    capsys.readouterr()

    fresh = str(tmp_path / "fresh.db")
    _point_at(monkeypatch, fresh)
    assert _run(monkeypatch, "import", "--file", str(ledger)) == 0
    capsys.readouterr()
    return fresh


#: 持仓表里**来自账本**的那几列。
#:
#: 另外几列（现价 / 市值 / 盈亏 / 盈亏率 / 币种）来自 `price_cache`，那是缓存
#: 不是账本——换个库自然就空了，`holdings sync` 一次就回来。往返比的是账本，
#: 备份要备的也是补不回来的东西。
_LEDGER_COLUMNS_OF_HOLDINGS = (
    "symbol",
    "name",
    "market",
    "asset_type",
    "quantity",
    "avg_cost",
    "total_fees",
)


def _ledger_part(db_path: str) -> list[dict]:
    df = portfolio_service.get_summary(db_path).holdings_df
    return [
        {column: record[column] for column in _LEDGER_COLUMNS_OF_HOLDINGS}
        for record in df.to_dict("records")
    ]


def test_the_ledger_can_be_imported_back(seeded, monkeypatch, capsys, tmp_path):
    """判据：导出的账本导进空库后，**账本那几列逐行一致**。

    这是「导出」这个功能的全部意义所在——报税那张表可以不往返，账本必须能。
    数量与成本价要一模不差地回来，包括那个 `10.05` 的加权成本。
    """
    before = _ledger_part(seeded)

    fresh = _round_trip(monkeypatch, tmp_path, seeded, capsys)

    assert before, "空对空相等是假绿"
    assert _ledger_part(fresh) == before


def test_the_price_cache_is_not_part_of_the_backup(seeded, monkeypatch, capsys, tmp_path):
    """上一条的另一半：说清「不一致的是哪几列、为什么」。

    行情不进账本文件。真把它写进去反而更坏——一份三个月前的备份导回来，
    那几个价格会看起来像今天的行情，而它们不是。
    """
    before = portfolio_service.get_summary(seeded).holdings_df

    fresh = _round_trip(monkeypatch, tmp_path, seeded, capsys)
    after = portfolio_service.get_summary(fresh).holdings_df

    assert not before["market_value"].isna().all(), "原库里那个标的本来是有市值的"
    assert after["market_value"].isna().all(), "新库没有行情缓存，市值应当算不出来"


def test_the_round_trip_keeps_both_portfolio_groups(seeded, monkeypatch, capsys, tmp_path):
    """组合分组跟着账本一起走：`account` 那一列就是 `portfolio_group`。

    丢了它，一份两账户的账本导回来会并成一个组，而用户在汇总里看不出来
    （B-32 花力气按账号分组，正是为了这个）。
    """
    fresh = _round_trip(monkeypatch, tmp_path, seeded, capsys)

    groups = {tx.portfolio_group for tx in transaction_dao.get_all(fresh)}
    assert groups == {"默认", "美股账户"}


def test_corporate_actions_survive_the_round_trip(make_tx, db_path, monkeypatch, capsys, tmp_path):
    """判据：分红与送转走一趟导出 / 导入，重算出来的持仓逐项一致。

    比的是**重算之后**的数量与成本价，不是落库的那几列——那几列本来就一样。
    公司行为的成本价是算出来的（分红摊薄 1005 → 955、送转折半到 4.775），
    所以只有往返之后重新重放一遍，才算验过它们能原样回去。
    """
    transaction_dao.add_many(
        db_path,
        [
            make_tx(qty=100.0, price=10.0, fee=5.0, trade_date=date(2025, 1, 1)),
            make_tx(trade_type="DIVIDEND", qty=100.0, price=0.5, trade_date=date(2025, 6, 1)),
            make_tx(trade_type="BONUS_SHARE", qty=100.0, price=0.0, trade_date=date(2025, 7, 1)),
        ],
    )
    before = _ledger_part(db_path)

    fresh = _round_trip(monkeypatch, tmp_path, db_path, capsys)

    assert before, "空对空相等是假绿"
    assert before[0]["quantity"] == pytest.approx(200.0)
    assert before[0]["avg_cost"] == pytest.approx(4.775)
    assert _ledger_part(fresh) == before


def test_the_numbers_come_back_bit_for_bit(make_tx, db_path, monkeypatch, capsys, tmp_path):
    """不做四舍五入：一个「不好看」的浮点数原样往返。

    导出时若为了文件好看把金额格式化到两位小数，文件是漂亮了，账本却变了
    ——而这是备份，不是报表。
    """
    ugly = 0.1 + 0.2
    transaction_dao.add(db_path, make_tx(symbol="600519", qty=3.0, price=ugly, fee=ugly))

    _point_at(monkeypatch, db_path)
    ledger = tmp_path / "ledger.csv"
    assert _run(monkeypatch, "export", "--out", str(ledger)) == 0
    capsys.readouterr()

    row = next(iter(csv.DictReader(ledger.read_text(encoding="utf-8-sig").splitlines())))
    assert row["price"] == repr(ugly), "写出来的不是原值，是被格式化过的"
    assert float(row["price"]) == ugly

    fresh = str(tmp_path / "fresh.db")
    _point_at(monkeypatch, fresh)
    assert _run(monkeypatch, "import", "--file", str(ledger)) == 0

    back = transaction_dao.get_all(fresh)[0]
    assert back.price == ugly
    assert back.fee == ugly


def test_the_only_thing_the_round_trip_loses_is_the_provenance(
    seeded, monkeypatch, capsys, tmp_path
):
    """往返丢的只有 `source`。

    它记的是「这笔是从哪份对账单读进来的」，而 canonical 格式里没有这一列，
    导回来一律记成 `csv`——这是句实话，这一行确实是从标准 CSV 读进来的。
    这条用例是**故意的**：把已知取舍钉住，免得日后有人当 bug 又「修」一遍。
    """
    fresh = _round_trip(monkeypatch, tmp_path, seeded, capsys)

    sources = {tx.source for tx in transaction_dao.get_all(fresh)}
    assert sources == {"csv"}
    assert {tx.source for tx in transaction_dao.get_all(seeded)} == {"demo-a", None}


# ------------------------------------------------------------------ 格式


def test_a_missing_number_is_an_empty_cell_not_the_word_nan(seeded, monkeypatch, tmp_path):
    """算不出来的值写成**空单元格**。

    写成 `nan` 的话，Excel 里看着像个词，拿它求和得到的是「没有」而不是报错，
    而这一列恰恰就是「只有取到行情的标的才算得出来」的那一列。
    """
    _point_at(monkeypatch, seeded)
    out_file = _export(monkeypatch, tmp_path, "holdings", "csv")

    text = out_file.read_text(encoding="utf-8-sig")
    rows = {row["symbol"]: row for row in csv.DictReader(text.splitlines())}

    assert rows["AAPL"]["market_value"] == ""
    assert rows["AAPL"]["profit_rate"] == ""
    assert rows["600519"]["market_value"] == "660.0", "取到行情的那一行得真的有数"
    assert "nan" not in text.lower()


def test_the_json_is_valid_json_with_null_instead_of_nan(seeded, monkeypatch, tmp_path):
    """JSON 里不许出现 `NaN`——它不是合法 JSON。

    `json.dumps` 默认会把 NaN 原样写出去，而 `jq` 与浏览器的 `JSON.parse` 读到
    就报错。所以这里用 `parse_constant` 严格解析：Python 自己的 `json.loads` 对
    `NaN` 是宽容的，拿它验等于没验。
    """
    _point_at(monkeypatch, seeded)
    out_file = _export(monkeypatch, tmp_path, "holdings", "json")

    text = out_file.read_text(encoding="utf-8")
    rows = json.loads(text, parse_constant=lambda c: pytest.fail(f"这不是合法 JSON：{c}"))

    aapl = next(row for row in rows if row["symbol"] == "AAPL")
    assert aapl["market_value"] is None
    assert aapl["profit"] is None


def test_no_dataset_carries_something_json_cannot_write(seeded):
    """三份数据都能被严格 `json.dumps` 写出——这是 `Dataset.rows` 的契约。

    不给 `allow_nan=False` 之外的任何宽容参数：漏进去一个 NaN 是 `ValueError`，
    漏进去一个 numpy 标量是 `TypeError`，这条都会指名道姓地报出来。
    """
    for what in export_service.BUILDERS:
        dataset = export_service.build(what, seeded)
        json.dumps(dataset.rows, allow_nan=False)


def test_the_csv_has_a_bom_and_still_imports_back(seeded, monkeypatch, tmp_path):
    """CSV 带 BOM：Excel 双击打开中文不乱码；本工具的导入第一个剥的就是 BOM。

    两处是一对，所以带 BOM 的导出**照样能导回来**，不是「为了 Excel 牺牲了
    往返」。这条把两头都走一遍。
    """
    _point_at(monkeypatch, seeded)
    out_file = _export(monkeypatch, tmp_path, "ledger", "csv")

    raw = out_file.read_bytes()
    assert raw.startswith(codecs.BOM_UTF8), "不带 BOM 的 CSV 在 Excel 里是乱码"
    assert "第一笔".encode() in raw

    # 本工具的编码探测认它，因此同一份文件导得回来
    assert brokers.decode_statement(raw).startswith("symbol,")


def test_the_csv_is_lf_like_the_rest_of_the_repo(seeded, monkeypatch, tmp_path):
    """行尾是 `\\n`（csv 模块默认给的是 `\\r\\n`）。"""
    _point_at(monkeypatch, seeded)

    assert b"\r\n" not in _export(monkeypatch, tmp_path, "ledger", "csv").read_bytes()


def test_the_holdings_export_has_exactly_the_columns_of_the_summary(seeded):
    """持仓表的列跟着服务层走：`get_summary` 加了列而导出没加，这条会红。

    导出列里比终端表格多一个 `currency`——那一列不进终端表格（人民币是默认
    口径），但少了它，一份含美股的持仓表就分不清哪一行的市值是美元（B-19）。
    """
    df = portfolio_service.get_summary(seeded).holdings_df

    assert set(export_service.holdings(seeded).columns) == set(df.columns)
    assert "currency" in export_service.holdings(seeded).columns


# ------------------------------------------------------------------ 命令层


def test_export_says_how_many_rows_went_where(seeded, monkeypatch, capsys, tmp_path):
    _point_at(monkeypatch, seeded)
    out_file = tmp_path / "ledger.csv"

    code = _run(monkeypatch, "export", "--out", str(out_file))
    out = capsys.readouterr().out

    assert code == 0
    assert out_file.exists()
    assert "已导出 3 行" in out
    assert str(out_file) in out, "得说清写到哪儿了"


def test_the_default_is_the_ledger(seeded, monkeypatch, capsys, tmp_path):
    """不给 `--what` 时导的是账本——三样里只有它能导回去，最该是默认。"""
    _point_at(monkeypatch, seeded)
    out_file = tmp_path / "out.csv"

    assert _run(monkeypatch, "export", "--out", str(out_file)) == 0

    assert out_file.read_text(encoding="utf-8-sig").startswith("symbol,market,")


def test_exporting_an_empty_database_says_why(db_path, monkeypatch, capsys, tmp_path):
    """空库不是错误：表头照写、0 行，并说清是「库里本来就没有」。

    静默给一个空文件最坏——用户分不清是「导出成功了但库是空的」还是
    「导出坏了」。
    """
    _point_at(monkeypatch, db_path)
    out_file = tmp_path / "ledger.csv"

    code = _run(monkeypatch, "export", "--out", str(out_file))
    out = capsys.readouterr().out

    assert code == 0
    assert "已导出 0 行" in out
    assert "还没有交易记录" in out
    assert out_file.read_text(encoding="utf-8-sig").splitlines() == [
        ",".join(export_service.ledger_columns())
    ]


def test_an_empty_json_export_is_an_empty_array(db_path, monkeypatch, capsys, tmp_path):
    _point_at(monkeypatch, db_path)

    assert json.loads(_export(monkeypatch, tmp_path, "snapshots", "json").read_text()) == []


def test_out_is_required(seeded, monkeypatch, capsys):
    _point_at(monkeypatch, seeded)

    code = _run(monkeypatch, "export")
    err = capsys.readouterr().err

    assert code == 5
    assert "错误（5）：" in err
    assert "--out" in err


def test_an_unknown_what_exits_5_without_a_traceback(seeded, monkeypatch, capsys, tmp_path):
    _point_at(monkeypatch, seeded)
    out_file = tmp_path / "x.csv"

    code = _run(monkeypatch, "export", "--what", "交易", "--out", str(out_file))
    err = capsys.readouterr().err

    assert code == 5
    assert "错误（5）：" in err
    assert "Traceback" not in err
    assert not out_file.exists(), "参数不合法就不该留下半份文件"


def test_the_choices_come_from_the_tables():
    """`--what` 与 `--format` 的取值从各自的表派生，命令里不另抄一份。

    抄一份的写法在加了第四样导出（或第三种格式）时不会报错，只会让那个新选项
    永远敲不出来。
    """
    from holdings.cli.commands.export import export_cmd
    from holdings.cli.renderers.export_renderer import WRITERS

    params = {param.name: param for param in export_cmd.params}

    assert list(params["what"].type.choices) == list(export_service.BUILDERS)
    assert list(params["fmt"].type.choices) == list(WRITERS)
