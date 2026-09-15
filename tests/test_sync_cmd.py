"""`holdings sync --market` 的默认值来自配置。

`default_market` 此前是 4 个「改了不起作用」的配置项之一：`sync` 的默认市场
硬编码成「全部」，用户把配置改成「美股」不会有任何变化。
"""

from __future__ import annotations

import sys
from datetime import date

import pytest

from holdings.cli.main import main
from holdings.data.fetcher import PriceResult
from holdings.models.enums import AssetType, MarketType, TradeType
from holdings.models.transaction import Transaction
from holdings.services import sync_service
from holdings.storage import transaction_dao


def _tx(symbol: str, market: MarketType) -> Transaction:
    return Transaction(
        symbol=symbol,
        market=market,
        asset_type=AssetType.STOCK,
        trade_date=date(2025, 1, 1),
        trade_type=TradeType.BUY,
        quantity=1.0,
        price=1.0,
    )


@pytest.fixture
def project(tmp_path, monkeypatch):
    """一个放着 config.yaml 与两种市场持仓的项目目录。"""
    db = tmp_path / "holdings.db"
    transaction_dao.add(str(db), _tx("600519", MarketType.A_SHARE))
    transaction_dao.add(str(db), _tx("AAPL", MarketType.US_STOCK))
    monkeypatch.chdir(tmp_path)

    def _write(config_body: str) -> None:
        (tmp_path / "config.yaml").write_text(
            f"database_path: {db}\n{config_body}", encoding="utf-8"
        )

    return _write


@pytest.fixture
def fetched(monkeypatch) -> list[str]:
    """记录实际发起过取价的标的（借此看出选了哪个市场）。"""
    symbols: list[str] = []

    def _fake(symbol, market):
        symbols.append(symbol)
        return PriceResult(symbol=symbol, price=1.0, source="fake")

    monkeypatch.setattr(sync_service.fetcher, "fetch_price", _fake)
    return symbols


def _run(monkeypatch, *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["holdings", "sync", *argv])
    try:
        main()
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


def test_market_default_comes_from_config(project, fetched, monkeypatch):
    """配置写「美股」，那么不带 --market 时就只同步美股。"""
    project("default_market: 美股\n")

    _run(monkeypatch)

    assert fetched == ["AAPL"]


def test_explicit_market_still_wins_over_the_config(project, fetched, monkeypatch):
    """配置只是默认值，命令行显式指定必须盖过它。"""
    project("default_market: 美股\n")

    _run(monkeypatch, "--market", "A股")

    assert fetched == ["600519"]


def test_default_when_config_is_absent_is_every_market(project, fetched, monkeypatch):
    """没有 config.yaml 时退回「全部」，与改动前的行为一致。"""
    project("")

    _run(monkeypatch)

    assert set(fetched) == {"600519", "AAPL"}


def test_invalid_default_market_is_reported_rather_than_ignored(project, capsys, monkeypatch):
    """配置里写了不存在的市场：报错退出，而不是悄悄按「全部」跑。

    静默回落会让用户以为配置生效了，实际同步的是另一个市场。
    """
    project("default_market: 港股\n")

    code = _run(monkeypatch)

    assert code == 5
    assert "港股" in capsys.readouterr().err
