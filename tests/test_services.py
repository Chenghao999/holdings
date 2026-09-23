"""services 层（portfolio_service / report_service / sync_service）的单元测试。

网络请求一律 monkeypatch，测试不触网。
"""

from datetime import date

import pandas as pd
import pytest

from holdings.data.fetcher import DataSourceUnavailableError, PriceResult
from holdings.models.enums import AssetType, MarketType
from holdings.models.snapshot import Snapshot
from holdings.portfolio import metrics
from holdings.services import portfolio_service, report_service, sync_service
from holdings.storage import price_cache_dao, snapshot_dao, transaction_dao

# ------------------------------------------------------------ portfolio_service


def test_summary_on_empty_db(db_path):
    summary = portfolio_service.get_summary(db_path)

    assert summary.total_value == 0.0
    assert summary.total_profit == 0.0
    assert summary.profit_rate == 0.0
    assert summary.holdings_df.empty
    assert summary.allocation == {}


def test_summary_single_buy_with_cached_price(db_path, make_tx):
    """费用摊入成本：avg_cost = (100*10 + 5) / 100 = 10.05。"""
    transaction_dao.add(db_path, make_tx(qty=100, price=10.0, fee=5.0))
    price_cache_dao.upsert(db_path, "600519", 12.0)

    summary = portfolio_service.get_summary(db_path)

    assert summary.total_value == pytest.approx(1200.0)
    assert summary.total_cost == pytest.approx(1005.0)
    assert summary.total_fees == pytest.approx(5.0)
    # 盈亏 = (12 - 10.05) * 100 - 5 = 190
    assert summary.total_profit == pytest.approx(190.0)
    assert summary.profit_rate == pytest.approx(190 / 1005 * 100)

    row = summary.holdings_df.iloc[0]
    assert row["symbol"] == "600519"
    assert row["market"] == "A股"
    assert row["asset_type"] == "stock"
    assert row["quantity"] == 100
    assert row["avg_cost"] == pytest.approx(10.05)
    assert row["current_price"] == 12.0
    assert row["market_value"] == pytest.approx(1200.0)
    assert row["profit"] == pytest.approx(190.0)

    assert summary.fee_breakdown == {"600519": 5.0}


def test_summary_without_cached_price_reports_unknown_not_zero(db_path, make_tx):
    """没有缓存价时是「不知道」，不是「值 0」。

    此前 current_price 缺省取 0.0，盈亏率于是算成 −100.00%——用户看到的是
    「血亏 100%」，而事实只是还没同步过。
    """
    transaction_dao.add(db_path, make_tx(qty=100, price=10.0, fee=0.0))

    summary = portfolio_service.get_summary(db_path)

    row = summary.holdings_df.iloc[0]
    assert pd.isna(row["current_price"])
    assert pd.isna(row["market_value"])
    assert pd.isna(row["profit"])
    assert pd.isna(row["profit_rate"])
    # 汇总里一个能定价的标的都没有：不是 0，是未知。B-19 把这个口径统一到了
    # 三个数上——此前 total_value / total_cost 仍是 0.0，由渲染层另外判断一次
    # 才显示成 `—`，两处口径迟早会对不上。
    assert summary.total_value is None
    assert summary.total_cost is None
    assert summary.total_profit is None
    assert summary.profit_rate is None
    # 但「谁没行情、它值多少成本」要如实报出来
    assert summary.unpriced_symbols == ["600519"]
    assert summary.unpriced_cost == pytest.approx(1000.0)


def test_summary_excludes_fully_sold_position(db_path, make_tx):
    """清仓标的不出现在持仓表里。"""
    transaction_dao.add(db_path, make_tx(qty=100, price=10.0))
    transaction_dao.add(
        db_path,
        make_tx(trade_type="SELL", qty=100, price=12.0, trade_date=date(2025, 2, 1)),
    )
    price_cache_dao.upsert(db_path, "600519", 12.0)

    summary = portfolio_service.get_summary(db_path)

    assert summary.holdings_df.empty
    assert summary.total_value == 0.0


def test_summary_allocation_splits_by_asset_type(db_path, make_tx):
    transaction_dao.add(db_path, make_tx(symbol="600519", asset_type=AssetType.STOCK))
    transaction_dao.add(db_path, make_tx(symbol="518880", asset_type=AssetType.GOLD, price=2.0))
    price_cache_dao.upsert(db_path, "600519", 20.0)
    price_cache_dao.upsert(db_path, "518880", 4.0)

    summary = portfolio_service.get_summary(db_path)

    assert summary.total_value == pytest.approx(2400.0)
    assert summary.allocation["stock"] == pytest.approx(2000 / 2400)
    assert summary.allocation["gold"] == pytest.approx(400 / 2400)


def test_summary_respects_group_filter(db_path, make_tx):
    transaction_dao.add(db_path, make_tx(symbol="A", group="默认"))
    transaction_dao.add(db_path, make_tx(symbol="B", group="打新"))

    summary = portfolio_service.get_summary(db_path, group="打新")

    assert list(summary.holdings_df["symbol"]) == ["B"]


# ---------------------------------------------------------------- sync_service


def _fake_price(price: float, source: str = "fake"):
    def _fetch(symbol, market):
        return PriceResult(symbol=symbol, price=price, currency="CNY", source=source)

    return _fetch


def test_sync_writes_price_into_cache(db_path, make_tx, monkeypatch):
    transaction_dao.add(db_path, make_tx(symbol="600519"))
    monkeypatch.setattr(sync_service.fetcher, "fetch_price", _fake_price(1680.5, "akshare"))

    result = sync_service.sync(db_path, MarketType.A_SHARE)

    assert result.updated == [{"symbol": "600519", "price": 1680.5, "source": "akshare"}]
    assert result.failed == []

    cached = price_cache_dao.get(db_path, "600519")
    assert cached.price == 1680.5
    assert cached.source == "akshare"


def test_sync_skips_fresh_cache(db_path, make_tx, monkeypatch):
    """TTL 内的标的不重复请求网络。"""
    transaction_dao.add(db_path, make_tx(symbol="600519"))
    monkeypatch.setattr(sync_service.fetcher, "fetch_price", _fake_price(10.0))

    sync_service.sync(db_path, MarketType.A_SHARE)
    second = sync_service.sync(db_path, MarketType.A_SHARE, ttl_seconds=300)

    assert second.updated == []
    assert second.failed == []


def test_sync_refetches_when_ttl_zero(db_path, make_tx, monkeypatch):
    transaction_dao.add(db_path, make_tx(symbol="600519"))
    monkeypatch.setattr(sync_service.fetcher, "fetch_price", _fake_price(10.0))
    sync_service.sync(db_path, MarketType.A_SHARE)

    monkeypatch.setattr(sync_service.fetcher, "fetch_price", _fake_price(20.0))
    second = sync_service.sync(db_path, MarketType.A_SHARE, ttl_seconds=0)

    assert second.updated == [{"symbol": "600519", "price": 20.0, "source": "fake"}]


def test_sync_collects_failure_without_raising(db_path, make_tx, monkeypatch):
    """单个标的失败不应中断整体同步。"""
    transaction_dao.add(db_path, make_tx(symbol="600519"))

    def _boom(symbol, market):
        raise DataSourceUnavailableError("akshare 超时")

    monkeypatch.setattr(sync_service.fetcher, "fetch_price", _boom)

    result = sync_service.sync(db_path, MarketType.A_SHARE)

    assert result.updated == []
    assert len(result.failed) == 1
    assert result.failed[0]["symbol"] == "600519"
    assert "akshare 超时" in result.failed[0]["error"]


def test_sync_partial_failure_keeps_successes(db_path, make_tx, monkeypatch):
    transaction_dao.add(db_path, make_tx(symbol="600519"))
    transaction_dao.add(db_path, make_tx(symbol="000001"))

    def _flaky(symbol, market):
        if symbol == "000001":
            raise DataSourceUnavailableError("boom")
        return PriceResult(symbol=symbol, price=10.0, source="fake")

    monkeypatch.setattr(sync_service.fetcher, "fetch_price", _flaky)

    result = sync_service.sync(db_path, MarketType.A_SHARE)

    assert [u["symbol"] for u in result.updated] == ["600519"]
    assert [f["symbol"] for f in result.failed] == ["000001"]


def test_sync_only_touches_target_market(db_path, make_tx, monkeypatch):
    transaction_dao.add(db_path, make_tx(symbol="600519", market=MarketType.A_SHARE))
    transaction_dao.add(db_path, make_tx(symbol="AAPL", market=MarketType.US_STOCK))
    monkeypatch.setattr(sync_service.fetcher, "fetch_price", _fake_price(10.0))

    result = sync_service.sync(db_path, MarketType.A_SHARE)

    assert [u["symbol"] for u in result.updated] == ["600519"]
    assert price_cache_dao.get(db_path, "AAPL") is None


def test_sync_on_empty_db_is_noop(db_path, monkeypatch):
    monkeypatch.setattr(
        sync_service.fetcher,
        "fetch_price",
        lambda *a, **k: pytest.fail("不应发起任何请求"),
    )

    result = sync_service.sync(db_path, MarketType.A_SHARE)

    assert result.updated == []
    assert result.failed == []


# ------------------------------------------------------------ chart_service


def test_chart_without_plotly_raises_missing_dependency(db_path, monkeypatch):
    """缺 plotly 时必须是 MissingDependencyError（退出码 6），而不是裸 RuntimeError。

    裸 RuntimeError 会绕过 main() 的映射层，用户看到的是 traceback。

    库要先有一条快照：`networth_figure` 是**先取数据再导入 plotly**，
    没有数据时抛的是「还没有任何快照」——数据为空是用户当场能处理的事，
    比「去装个包」更该先说。
    """
    import sys

    from holdings.exceptions import HoldingsError, MissingDependencyError
    from holdings.services import chart_service

    snapshot_dao.add(db_path, _snap(1, 1000.0))

    # 把子模块置为 None 是模拟 ImportError 的标准做法
    monkeypatch.setitem(sys.modules, "plotly", None)
    monkeypatch.setitem(sys.modules, "plotly.graph_objects", None)

    with pytest.raises(MissingDependencyError) as exc:
        chart_service.networth_figure(db_path)

    assert issubclass(MissingDependencyError, HoldingsError)
    # 提示必须给出可执行的安装命令，而不是只说「未安装」
    assert "holdings-cli[chart]" in str(exc.value)


# ----------------------------------------------------------- report_service


def _snap(day: int, total: float, month: int = 1) -> Snapshot:
    return Snapshot(
        snapshot_date=date(2025, month, day),
        total_value=total,
        equity_value=total,
        gold_value=0.0,
    )


def _add_snaps(db_path: str, *rows: tuple[int, int, float]) -> None:
    """rows 为 (月, 日, 净值)。"""
    for month, day, total in rows:
        snapshot_dao.add(db_path, _snap(day, total, month))


def test_performance_on_empty_db_reports_no_snapshots(db_path):
    perf = report_service.get_performance(db_path)

    assert perf.snapshot_count == 0
    assert perf.max_drawdown is None
    assert perf.annualized_return is None
    assert perf.sharpe is None


def test_performance_with_a_single_snapshot_is_all_unknown(db_path):
    """单点不能算出「回撤 0.00%」——那看着像结论，其实只是没有第二个点。"""
    _add_snaps(db_path, (1, 1, 100.0))

    perf = report_service.get_performance(db_path)

    assert perf.snapshot_count == 1
    assert perf.max_drawdown is None, "单点回撤必须是 None，不是 0.0"


def test_performance_max_drawdown_of_known_series(db_path):
    """BACKLOG B-02 的判据：100 / 120 / 90 / 110 → (120-90)/120 = 25%。"""
    _add_snaps(db_path, (1, 1, 100.0), (2, 1, 120.0), (3, 1, 90.0), (4, 1, 110.0))

    perf = report_service.get_performance(db_path)

    assert perf.snapshot_count == 4
    assert perf.max_drawdown == pytest.approx(0.25)
    assert (perf.first_date, perf.last_date) == (date(2025, 1, 1), date(2025, 4, 1))


def test_performance_annualizes_on_the_real_span_not_the_point_count(db_path):
    """90 天的跨度必须按 90 天折算，拿点数当交易日会算出一个大得多的数。"""
    _add_snaps(db_path, (1, 1, 100.0), (2, 1, 120.0), (3, 1, 90.0), (4, 1, 110.0))

    perf = report_service.get_performance(db_path)

    years = 90 / metrics.DAYS_PER_YEAR
    assert perf.annualized_return == pytest.approx((110.0 / 100.0) ** (1 / years) - 1)


def test_performance_computes_sharpe_for_a_regular_monthly_series(db_path):
    _add_snaps(db_path, (1, 1, 100.0), (2, 1, 120.0), (3, 1, 90.0), (4, 1, 110.0))

    perf = report_service.get_performance(db_path)

    assert perf.sharpe is not None
    assert perf.notes == [], "口径都成立时不该有任何说明行"


def test_performance_skips_sharpe_when_intervals_are_irregular(db_path):
    """快照间隔忽长忽短时算不出有意义的夏普，返回 None 并说明原因。"""
    _add_snaps(
        db_path,
        (1, 1, 100.0),
        (1, 8, 110.0),
        (2, 1, 120.0),
        (3, 1, 130.0),
    )

    perf = report_service.get_performance(db_path)

    assert perf.sharpe is None
    assert any("间隔不规律" in note for note in perf.notes)
    assert perf.max_drawdown is not None, "夏普算不出来不影响回撤——回撤不要求等距"


def test_performance_skips_annualized_below_the_minimum_span(db_path):
    """相隔几天的两次快照能外推出天文数字的年化收益，那是无用的数。"""
    _add_snaps(db_path, (1, 1, 100.0), (1, 3, 110.0))

    perf = report_service.get_performance(db_path)

    assert perf.annualized_return is None
    assert any(str(report_service.MIN_DAYS_FOR_ANNUALIZED) in note for note in perf.notes)
    assert perf.max_drawdown == pytest.approx(0.0)


def test_performance_skips_annualized_when_the_first_snapshot_is_zero(db_path):
    _add_snaps(db_path, (1, 1, 0.0), (2, 1, 120.0), (3, 1, 90.0))

    perf = report_service.get_performance(db_path)

    assert perf.annualized_return is None
    assert any("净值为 0" in note for note in perf.notes)
