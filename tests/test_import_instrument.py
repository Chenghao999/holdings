"""导入时按代码补全市场与资产类型（B-32）。

券商 CSV 里通常只有代码，此前 `market` 缺省成 A 股、`asset_type` 缺省成 stock，
一份美股对账单整份被记成 A 股。这一组锁的是**补全这条路**：什么时候去问、
问哪个市场、问不到怎么办、以及文件自己写了的时候听谁的。

不触网：数据源一律打桩成脚本化的假实现（`conftest.no_network` 已经把真源清空）。
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from holdings.cli.commands.import_cmd import import_cmd
from holdings.data import instrument, sources
from holdings.data.fetcher import DataSourceUnavailableError, SymbolNotFoundError
from holdings.models.asset_meta import AssetMeta
from holdings.models.enums import AssetType, MarketType
from holdings.storage import asset_meta_dao, db, transaction_dao

#: 只有代码的对账单：市场、资产类型两列都没有。
BARE_HEADER = "symbol,trade_date,trade_type,quantity,price\n"


@pytest.fixture
def fake_sources(monkeypatch):
    """把数据源表换成脚本化的假实现，返回调用记录 `(代码, 被问的市场)`。

    用法：`calls = fake_sources({MarketType.US_STOCK: 资料或异常})`——
    **没列出来的市场等于「没有源」**，与黄金的处境一样。
    """
    calls: list[tuple[str, MarketType]] = []

    def _install(answers):
        table: dict[MarketType, dict[str, sources.Source[instrument.SymbolInfo]]] = {}
        for market, answer in answers.items():

            def _fake(symbol, _market=market, _answer=answer):
                calls.append((symbol, _market))
                if isinstance(_answer, Exception):
                    raise _answer
                return _answer

            table[market] = {"fake": _fake}
        monkeypatch.setattr(instrument, "_SOURCES", table)
        monkeypatch.setattr(sources, "priority_for", lambda market, key="priority": ["fake"])
        return calls

    return _install


@pytest.fixture
def run_import(tmp_path, monkeypatch):
    """写一份对账单并执行导入，返回 (result, 库路径)。"""

    def _run(text: str, *extra: str):
        monkeypatch.chdir(tmp_path)
        csv_file = tmp_path / "in.csv"
        csv_file.write_bytes(text.encode("utf-8"))
        result = CliRunner().invoke(import_cmd, ["--file", str(csv_file), *extra])
        return result, str(tmp_path / "data" / "holdings.db")

    return _run


def _info(symbol: str, market: MarketType, name="某标的", asset_type=None, source="fake"):
    return instrument.SymbolInfo(
        symbol=symbol, name=name, market=market, asset_type=asset_type, source=source
    )


def _stored(db_path: str) -> list:
    return transaction_dao.get_all(db_path)


def _markets_tried(calls: list[tuple[str, MarketType]]) -> list[MarketType]:
    """问过哪几个市场，**按顺序，去掉重试的重复**。

    失败的源会被 `fetch_with_fallback` 按 `sync.retry_count` 重试，调用记录
    里因此有重复项——那是重试的份（`tests/test_resilience.py` 管的事），
    这一组用例只关心**问的顺序**。
    """
    return list(dict.fromkeys(market for _, market in calls))


# ---------------------------------------------------------------- 判据一


def test_a_statement_without_a_market_column_is_no_longer_all_a_share(run_import, fake_sources):
    """判据一：只写代码的 CSV 能导进来，且市场不再是清一色的默认值。"""
    fake_sources({MarketType.US_STOCK: _info("AAPL", MarketType.US_STOCK, "苹果")})

    result, db_path = run_import(BARE_HEADER + "AAPL,2025-01-02,BUY,10,100\n")

    assert result.exit_code == 0
    assert [tx.market for tx in _stored(db_path)] == [MarketType.US_STOCK]


def test_the_market_that_lands_is_the_one_the_source_named(run_import, fake_sources):
    """按代码形状排的是**问的顺序**，不是结论——落库的市场是数据源说的。"""
    fake_sources({MarketType.A_SHARE: _info("000001", MarketType.A_SHARE, "平安银行")})

    _, db_path = run_import(BARE_HEADER + "000001,2025-01-02,BUY,10,100\n")

    assert [tx.market for tx in _stored(db_path)] == [MarketType.A_SHARE]


def test_asset_type_is_filled_from_the_source(run_import, fake_sources):
    fake_sources(
        {MarketType.A_SHARE: _info("518880", MarketType.A_SHARE, asset_type=AssetType.ETF)}
    )

    _, db_path = run_import(BARE_HEADER + "518880,2025-01-02,BUY,100,5\n")

    assert [tx.asset_type for tx in _stored(db_path)] == [AssetType.ETF]


def test_a_six_digit_code_is_asked_about_a_share_first(fake_sources):
    """形状只决定先问谁：akshare 取一次资料要拉整张全市场表，别拿美股代码去问它。"""
    calls = fake_sources(
        {
            MarketType.A_SHARE: _info("600519", MarketType.A_SHARE),
            MarketType.US_STOCK: _info("600519", MarketType.US_STOCK),
        }
    )

    from holdings.services import asset_meta_service

    asset_meta_service.lookup(":memory:", "600519")

    assert calls == [("600519", MarketType.A_SHARE)]


def test_a_lettered_code_is_asked_about_the_us_market_first(fake_sources):
    calls = fake_sources(
        {
            MarketType.A_SHARE: _info("AAPL", MarketType.A_SHARE),
            MarketType.US_STOCK: _info("AAPL", MarketType.US_STOCK),
        }
    )

    from holdings.services import asset_meta_service

    asset_meta_service.lookup(":memory:", "AAPL")

    assert calls == [("AAPL", MarketType.US_STOCK)]


def test_the_next_market_is_tried_when_the_first_one_does_not_know_the_code(
    run_import, fake_sources
):
    """第一个市场说「没这个标的」时接着问下一个——这正是形状猜错时的退路。"""
    calls = fake_sources(
        {
            MarketType.A_SHARE: SymbolNotFoundError("这张表里没有"),
            MarketType.US_STOCK: _info("600519", MarketType.US_STOCK),
        }
    )

    _, db_path = run_import(BARE_HEADER + "600519,2025-01-02,BUY,10,100\n")

    assert _markets_tried(calls) == [MarketType.A_SHARE, MarketType.US_STOCK]
    assert [tx.market for tx in _stored(db_path)] == [MarketType.US_STOCK]


# ---------------------------------------------------------------- 文件说了算


def test_the_file_wins_over_the_data_source(run_import, fake_sources):
    """对账单自己写了市场就以它为准——它比按代码形状排的顺序准。

    查资料仍然做（名称要落进 `asset_meta`，`holdings list` 才显示得出来），
    但**不许覆盖文件写的那两列**。
    """
    calls = fake_sources(
        {MarketType.US_STOCK: _info("600519", MarketType.US_STOCK, asset_type=AssetType.STOCK)}
    )

    _, db_path = run_import(
        "symbol,market,trade_date,trade_type,quantity,price\n600519,美股,2025-01-02,BUY,10,100\n"
    )

    assert calls == [("600519", MarketType.US_STOCK)], "用文件里的市场去问，不按形状猜"
    assert [tx.market for tx in _stored(db_path)] == [MarketType.US_STOCK]


# ---------------------------------------------------------------- 判据三：取不到


def test_a_failed_lookup_does_not_block_the_import(run_import, fake_sources):
    """判据三：取不到资料时（离线）导入仍然成功。"""
    fake_sources(
        {
            MarketType.A_SHARE: DataSourceUnavailableError("没网"),
            MarketType.US_STOCK: DataSourceUnavailableError("没网"),
        }
    )

    result, db_path = run_import(BARE_HEADER + "600519,2025-01-02,BUY,10,100\n")

    assert result.exit_code == 0
    assert len(_stored(db_path)) == 1
    assert [tx.market for tx in _stored(db_path)] == [MarketType.A_SHARE], "沿用默认值"


def test_the_rows_that_used_the_default_are_named(run_import, fake_sources):
    """判据三的另一半：提示里说清了哪些行用的是默认值。

    不说明就等于把默认值当成了事实——用户没有别的办法看出来。
    """
    fake_sources({MarketType.A_SHARE: DataSourceUnavailableError("没网")})

    result, _ = run_import(
        BARE_HEADER + "600519,2025-01-02,BUY,10,100\nAAPL,2025-01-03,BUY,10,100\n"
    )

    assert "标的资料：2 行有列按默认值记" in result.output
    assert "第 2 行市场没取到，按默认值记：A股" in result.output
    assert "第 3 行资产类型没取到，按默认值记：stock" in result.output


def test_a_fully_resolved_import_does_not_warn(run_import, fake_sources):
    """全都取到了就不该出现「没取到」——一句恒真的提醒等于没有提醒。"""
    fake_sources(
        {MarketType.A_SHARE: _info("600519", MarketType.A_SHARE, asset_type=AssetType.STOCK)}
    )

    result, _ = run_import(BARE_HEADER + "600519,2025-01-02,BUY,10,100\n")

    assert "标的资料：全部取自对账单或数据源" in result.output
    assert "按默认值记" not in result.output


def test_only_the_column_that_fell_back_is_reported(run_import, fake_sources):
    """只补上了市场、资产类型没问到，就只说资产类型。

    说成「这一行没取到资料」是假话：用户会以为市场也是默认值，转头用
    `holdings meta` 去改一个本来就对的字段。
    """
    fake_sources({MarketType.A_SHARE: _info("600519", MarketType.A_SHARE)})

    result, _ = run_import(BARE_HEADER + "600519,2025-01-02,BUY,10,100\n")

    assert "标的资料：1 行有列按默认值记" in result.output
    assert "第 2 行资产类型没取到，按默认值记：stock" in result.output
    assert "市场没取到" not in result.output


def test_a_row_whose_data_all_came_from_the_file_is_not_reported(run_import, fake_sources):
    """两列都写在文件里时不报默认值——它压根没用到默认值。

    但资料照样查（名称要落进 `asset_meta`），查不到也不该反过来报一句。
    """
    fake_sources({MarketType.A_SHARE: DataSourceUnavailableError("没网")})

    result, _ = run_import(
        "symbol,market,asset_type,trade_date,trade_type,quantity,price\n"
        "600519,A股,stock,2025-01-02,BUY,10,100\n"
    )

    assert "标的资料：全部取自对账单或数据源" in result.output
    assert "按默认值记" not in result.output


def test_a_statement_with_nothing_posted_says_nothing_about_instruments(run_import):
    """一行都没入账时印「全部取自对账单或数据源」是拿 0 当成绩。"""
    result, _ = run_import(
        "symbol,trade_date,trade_type,quantity,price,fee\n600519,2025-01-02,分红派息,0,0,100\n"
    )

    assert "标的资料" not in result.output


# ---------------------------------------------------------------- 时机与次数


def test_the_source_is_asked_once_per_symbol(run_import, fake_sources):
    """对账单里一个标的会出现很多行，逐行去问是白问。"""
    calls = fake_sources({MarketType.A_SHARE: _info("600519", MarketType.A_SHARE)})

    run_import(
        BARE_HEADER
        + "600519,2025-01-02,BUY,10,100\n"
        + "600519,2025-01-03,BUY,10,100\n"
        + "600519,2025-01-04,BUY,10,100\n",
        "--dedupe",
        "off",
    )

    assert calls == [("600519", MarketType.A_SHARE)]


def test_nothing_is_fetched_when_the_import_is_aborted(run_import, fake_sources):
    """取资料会联网、还会写 `asset_meta` 缓存，所以放在校验与查重**之后**。

    一次整批中止的导入不该留下任何痕迹——连一个网络请求都不该发出去。
    """
    calls = fake_sources({MarketType.A_SHARE: _info("600519", MarketType.A_SHARE)})

    run_import(BARE_HEADER + "600519,2025-01-02,BUY,10,100\n" + "600519,not-a-date,BUY,10,100\n")

    assert calls == []


def test_the_name_lands_in_asset_meta(run_import, fake_sources):
    """顺带的收获：`holdings list` 的名称列取自 `asset_meta`，导入后就有名字了。"""
    fake_sources({MarketType.A_SHARE: _info("600519", MarketType.A_SHARE, "贵州茅台")})

    _, db_path = run_import(BARE_HEADER + "600519,2025-01-02,BUY,10,100\n")

    stored = asset_meta_dao.get(db_path, "600519")
    assert stored is not None
    assert (stored.name, stored.market) == ("贵州茅台", MarketType.A_SHARE.value)


def test_a_broken_market_in_the_meta_table_does_not_break_the_import(run_import, monkeypatch):
    """`asset_meta.market` 是字符串，转不回枚举时当作没查到，而不是让整份账单导不进来。

    转不回来要么是用户在 `holdings meta` 里手填了个不存在的市场，要么是更早的
    版本写坏了库——两种都不该让导入失败，也不该拿个瞎猜的市场顶上。
    """
    from holdings.services import asset_meta_service

    monkeypatch.setattr(
        asset_meta_service,
        "lookup",
        lambda db_path, symbol, market=None, ttl_seconds=None: AssetMeta(
            symbol=symbol, name="名字有", market="火星"
        ),
    )

    result, db_path = run_import(BARE_HEADER + "600519,2025-01-02,BUY,10,100\n")

    assert result.exit_code == 0
    assert [tx.market for tx in _stored(db_path)] == [MarketType.A_SHARE], "退回默认值"
    assert "第 2 行市场没取到，按默认值记：A股" in result.output


def test_the_meta_table_is_usable_after_the_import(run_import, fake_sources):
    """落库的市场确实写进了 `transactions`，不是只在内存里换了一下。"""
    fake_sources({MarketType.US_STOCK: _info("AAPL", MarketType.US_STOCK)})

    _, db_path = run_import(BARE_HEADER + "AAPL,2025-01-02,BUY,10,100\n")

    with db.connect(db_path) as conn:
        row = conn.execute("SELECT market, asset_type FROM transactions").fetchone()
    assert (row["market"], row["asset_type"]) == (MarketType.US_STOCK.value, AssetType.STOCK.value)
