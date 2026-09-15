"""services 层（portfolio_service / sync_service）的单元测试。

网络请求一律 monkeypatch，测试不触网。
"""

from datetime import date

import pytest

from holdings.data.fetcher import DataSourceUnavailableError, PriceResult
from holdings.models.enums import AssetType, MarketType
from holdings.services import portfolio_service, sync_service
from holdings.storage import price_cache_dao, transaction_dao

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


def test_summary_without_cached_price_uses_zero(db_path, make_tx):
    """没有缓存价时不臆造价格，市值为 0。"""
    transaction_dao.add(db_path, make_tx(qty=100, price=10.0, fee=0.0))

    summary = portfolio_service.get_summary(db_path)

    row = summary.holdings_df.iloc[0]
    assert row["current_price"] == 0.0
    assert row["market_value"] == 0.0
    assert summary.total_value == 0.0
    # 盈亏 = (0 - 10) * 100 - 0 = -1000
    assert summary.total_profit == pytest.approx(-1000.0)


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
