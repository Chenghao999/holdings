"""网络调用的超时：`sync` 不该被一个不响应的数据源挂死。

这一层此前完全没有实现——`sync.timeout_seconds` 是个没人读的配置项，
上游卡住时 `holdings sync` 会一直等下去，用户只能 Ctrl-C。
"""

from __future__ import annotations

import sys
import threading
import time

import pytest

from holdings.cli.main import main
from holdings.data import resilience
from holdings.data.fetcher import DataSourceUnavailableError, PriceResult, SymbolNotFoundError
from holdings.models.enums import MarketType
from holdings.services import sync_service
from holdings.storage import transaction_dao

# 模拟「不响应的上游」：卡在一个永不置位的事件上，而不是 sleep(N)。
# 用 sleep 的话每个用例都要真等满 N 秒（B-10 明确要求整个 tests/ 不许有真实
# 等待）；事件既等价——永远不返回——又不花时间。
_NEVER = threading.Event()
_TIMEOUT = 0.05


def _hang(symbol, market):
    _NEVER.wait()
    return PriceResult(symbol=symbol, price=1.0)


def _buy():
    from datetime import date

    from holdings.models.enums import AssetType, TradeType
    from holdings.models.transaction import Transaction

    return Transaction(
        symbol="600519",
        market=MarketType.A_SHARE,
        asset_type=AssetType.STOCK,
        trade_date=date(2025, 1, 1),
        trade_type=TradeType.BUY,
        quantity=100.0,
        price=10.0,
    )


# ------------------------------------------------------------ call_with_timeout


def test_returns_the_value_when_it_finishes_in_time():
    assert resilience.call_with_timeout(lambda: "ok", 5) == "ok"


def test_passes_arguments_through():
    assert resilience.call_with_timeout(lambda a, b: a + b, 5, 1, 2) == 3


def test_propagates_the_original_exception_type():
    """在调用方看来要和直接调用一模一样，否则 `except SymbolNotFoundError` 会漏。"""

    def _boom():
        raise SymbolNotFoundError("没有这个标的")

    with pytest.raises(SymbolNotFoundError):
        resilience.call_with_timeout(_boom, 5)


def test_gives_up_and_reports_after_the_budget():
    started = time.monotonic()

    with pytest.raises(DataSourceUnavailableError):
        resilience.call_with_timeout(_NEVER.wait, 0.2)

    assert time.monotonic() - started < 5, "必须在预算内返回，而不是一直等下去"


def test_non_positive_budget_means_no_limit():
    """配置里写 0 的用户要的是「别管我」，不是「立刻超时」。"""
    assert resilience.call_with_timeout(lambda: "ok", 0) == "ok"
    assert resilience.call_with_timeout(lambda: "ok", -1) == "ok"


def test_timeout_thread_does_not_block_interpreter_exit():
    """被放弃的请求仍在后台跑，但它必须是守护线程——否则进程退不出去。

    这条正是「线程超时」方案能否成立的关键：普通（非守护）线程会让
    Python 在退出时一直等它，超时省下的时间又在出口处还回去。
    """
    with pytest.raises(DataSourceUnavailableError):
        resilience.call_with_timeout(_NEVER.wait, 0.2)

    stragglers = [t for t in threading.enumerate() if t.name == "holdings-fetch"]
    assert stragglers, "超时后线程应仍活着（我们只是不等它）"
    assert all(t.daemon for t in stragglers), "非守护线程会拖住进程退出，超时省下的时间就白省了"


# ------------------------------------------------------------------ sync 层


def test_sync_records_timeout_as_a_failure_instead_of_hanging(db_path, make_tx, monkeypatch):
    transaction_dao.add(db_path, make_tx(symbol="600519"))
    monkeypatch.setattr(sync_service.fetcher, "fetch_price", _hang)

    started = time.monotonic()
    result = sync_service.sync(db_path, MarketType.A_SHARE, timeout_seconds=_TIMEOUT)
    elapsed = time.monotonic() - started

    assert elapsed < 5
    assert result.updated == []
    assert [f["symbol"] for f in result.failed] == ["600519"]
    assert "秒" in result.failed[0]["error"]


def test_one_hanging_symbol_does_not_stop_the_others(db_path, make_tx, monkeypatch):
    """单个标的超时只损失它自己，其余标的照常同步。"""
    transaction_dao.add(db_path, make_tx(symbol="600519"))
    transaction_dao.add(db_path, make_tx(symbol="000001"))

    def _only_first_hangs(symbol, market):
        if symbol == "600519":
            return _hang(symbol, market)
        return PriceResult(symbol=symbol, price=8.8, source="fake")

    monkeypatch.setattr(sync_service.fetcher, "fetch_price", _only_first_hangs)

    result = sync_service.sync(db_path, MarketType.A_SHARE, timeout_seconds=_TIMEOUT)

    assert [u["symbol"] for u in result.updated] == ["000001"]
    assert [f["symbol"] for f in result.failed] == ["600519"]


# ------------------------------------------------------------------ 命令层


def test_sync_command_returns_instead_of_hanging(tmp_path, monkeypatch, capsys):
    """BACKLOG B-05 的判据：timeout_seconds 改成 1 后，命令在 ~1 秒内返回且退出码 1。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text(
        "database_path: holdings.db\nsync:\n  timeout_seconds: 1\n", encoding="utf-8"
    )
    db = tmp_path / "holdings.db"
    transaction_dao.add(str(db), _buy())
    monkeypatch.setattr(sync_service.fetcher, "fetch_price", _hang)
    monkeypatch.setattr(sys, "argv", ["holdings", "sync", "--market", "A股"])

    started = time.monotonic()
    with pytest.raises(SystemExit) as exc:
        main()
    elapsed = time.monotonic() - started

    assert elapsed < 5, f"命令挂住了：耗时 {elapsed:.1f} 秒"
    assert exc.value.code == 1, "全部标的同步失败应返回退出码 1"
    assert "600519" in capsys.readouterr().out
