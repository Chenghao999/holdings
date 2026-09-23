"""`holdings web`：只读看板。

数据全部来自 `services/`——新层的依赖方向（只 import `services`，不 import
`cli` / `tui`）由 `test_layering.py` 守着，这里测的是「页面上的数对不对」。

看板用 `TestClient` 直接打请求，不起真服务器：起服务只多出端口冲突这一种
偶发失败，测不到任何额外的东西。
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from types import SimpleNamespace

import pytest

from holdings.cli.main import main
from holdings.models.enums import AssetType, MarketType, TradeType
from holdings.models.snapshot import Snapshot
from holdings.models.transaction import Transaction
from holdings.services import portfolio_service
from holdings.storage import price_cache_dao, snapshot_dao
from holdings.storage.transaction_dao import add_many

requires_fastapi = pytest.mark.skipif(
    importlib.util.find_spec("fastapi") is None,
    reason="需要 fastapi（dev extra 里有；本地跑 pip install fastapi jinja2 httpx）",
)
requires_plotly = pytest.mark.skipif(
    importlib.util.find_spec("plotly") is None,
    reason="需要 plotly（chart extra）",
)


def _seed(db_path: str) -> None:
    add_many(
        db_path,
        [
            Transaction(
                symbol="518880",
                market=MarketType.A_SHARE,
                asset_type=AssetType.STOCK,
                trade_date=date(2025, 1, 1),
                trade_type=TradeType.BUY,
                quantity=1000.0,
                price=4.85,
                fee=5.0,
            ),
            Transaction(
                symbol="600519",
                market=MarketType.A_SHARE,
                asset_type=AssetType.STOCK,
                trade_date=date(2025, 1, 1),
                trade_type=TradeType.BUY,
                quantity=100.0,
                price=1680.5,
            ),
        ],
    )
    price_cache_dao.upsert(db_path, "518880", 5.1, "CNY", "test")


def _seed_snapshots(db_path: str) -> None:
    for month, total in ((1, 100.0), (2, 120.0), (3, 90.0), (4, 110.0)):
        snapshot_dao.add(
            db_path,
            Snapshot(
                snapshot_date=date(2025, month, 1),
                total_value=total,
                equity_value=total,
                gold_value=0.0,
            ),
        )


def _client(db_path: str):
    from fastapi.testclient import TestClient

    from holdings.web.app import create_app

    return TestClient(create_app(db_path))


def _exit_code(monkeypatch, *argv: str) -> tuple[int, str, str]:
    """按用户那样跑一遍入口，返回（退出码, stdout, stderr）。"""
    import contextlib
    import io

    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr(sys, "argv", ["holdings", *argv])
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            main()
        except SystemExit as exc:
            return int(exc.code or 0), out.getvalue(), err.getvalue()
    return 0, out.getvalue(), err.getvalue()


# ------------------------------------------------------------------ 缺依赖


def test_without_the_web_extra_exits_6_with_an_install_hint(monkeypatch, tmp_path):
    """fastapi / uvicorn 是可选依赖，缺了要按「缺依赖」的契约报（退出码 6）。

    漏一个 ImportError 出去就会绕过 main() 的映射层，用户看到的只是裸 traceback。
    """
    monkeypatch.setitem(sys.modules, "uvicorn", None)
    monkeypatch.chdir(tmp_path)

    code, _, err = _exit_code(monkeypatch, "web")

    assert code == 6
    assert "错误（6）：" in err
    assert "holdings-cli[web]" in err, "要给出可执行的安装命令"


# ------------------------------------------------------------------ 命令层


@requires_fastapi
def test_the_command_hands_the_app_to_uvicorn(monkeypatch, tmp_path, db_path):
    """`holdings web` 只做三件事：读配置、建应用、交给 uvicorn。

    用一个假的 uvicorn 模块接住调用——起真服务器要占端口，而这一条要断言的
    是「交给它的是什么」。
    """
    calls: dict = {}
    fake = SimpleNamespace(run=lambda app, **kwargs: calls.update(kwargs, app=app))
    monkeypatch.setitem(sys.modules, "uvicorn", fake)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text(f"database_path: {db_path}\n", encoding="utf-8")

    code, _, _ = _exit_code(monkeypatch, "web", "--host", "0.0.0.0", "--port", "9999")

    assert code == 0
    assert calls["host"] == "0.0.0.0"
    assert calls["port"] == 9999
    assert calls["app"].title == "holdings"


@requires_fastapi
def test_the_defaults_are_local_only(monkeypatch, tmp_path, db_path):
    """默认只绑本机回环：这是个把全部持仓摊开的页面，不该开局域网可见。"""
    calls: dict = {}
    fake = SimpleNamespace(run=lambda app, **kwargs: calls.update(kwargs))
    monkeypatch.setitem(sys.modules, "uvicorn", fake)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text(f"database_path: {db_path}\n", encoding="utf-8")

    _exit_code(monkeypatch, "web")

    assert calls["host"] == "127.0.0.1"


# ------------------------------------------------------------------ 看板


@requires_fastapi
def test_the_dashboard_lists_the_holdings(db_path):
    """BACKLOG B-20 的判据：看板能起、能看到真实数据。"""
    _seed(db_path)

    html = _client(db_path).get("/").text

    assert "518880" in html
    assert "600519" in html
    assert "5.1000" in html, "现价按单价口径显示（四位小数）"
    assert "总市值" in html


@requires_fastapi
def test_an_empty_database_says_so_instead_of_showing_a_bare_table(db_path):
    html = _client(db_path).get("/").text

    assert "还没有持仓" in html


@requires_fastapi
def test_the_table_uses_the_shared_column_contract(db_path):
    """表头取自服务层那份列契约，不另写一份——三个界面显示的是同一张表。"""
    _seed(db_path)

    html = _client(db_path).get("/").text

    for label in portfolio_service.HOLDINGS_COLUMNS.values():
        assert f">{label}<" in html, f"表头少了「{label}」"


@requires_fastapi
def test_the_numbers_match_the_service(db_path):
    """页面上印的数就是服务层算出来的数，页面自己不重算。"""
    from holdings.utils.formatter import format_money, format_percent

    _seed(db_path)
    summary = portfolio_service.get_summary(db_path)

    html = _client(db_path).get("/").text

    assert format_money(summary.total_value) in html
    assert format_percent(summary.profit_rate) in html


@requires_fastapi
def test_unpriced_symbols_are_flagged(db_path):
    """没同步过时页面也要说清，而不是显一个不存在的亏损——与 CLI 同口径。"""
    _seed(db_path)

    html = _client(db_path).get("/").text

    assert "1 个标的无行情" in html


@requires_fastapi
def test_foreign_symbols_are_flagged(db_path):
    """美元标的也要说清「没算进去」——与 CLI、TUI 同口径（B-19）。"""
    _seed(db_path)
    add_many(
        db_path,
        [
            Transaction(
                symbol="AAPL",
                market=MarketType.US_STOCK,
                asset_type=AssetType.STOCK,
                trade_date=date(2025, 1, 1),
                trade_type=TradeType.BUY,
                quantity=10.0,
                price=100.0,
            )
        ],
    )
    price_cache_dao.upsert(db_path, "AAPL", 200.0, "USD", "test")

    html = _client(db_path).get("/").text

    assert "1 个标的以美元计价" in html
    # 外币的现价要带上币种，否则同一列里混着两种货币而不说明。
    assert "200.0000 USD" in html


@requires_fastapi
def test_nothing_can_be_priced_shows_a_dash_not_a_zero(db_path):
    """一个标的都计不进来时显示 `—`：`0.00` 看着像空仓，事实是算不出来。"""
    add_many(
        db_path,
        [
            Transaction(
                symbol="600519",
                market=MarketType.A_SHARE,
                asset_type=AssetType.STOCK,
                trade_date=date(2025, 1, 1),
                trade_type=TradeType.BUY,
                quantity=100.0,
                price=1680.5,
            )
        ],
    )

    html = _client(db_path).get("/").text

    assert "—" in html
    assert "0.00" not in html.split("累计费用")[0].split("总市值")[-1], "总市值不该是 0.00"


# ------------------------------------------------------------------ 报表页


@requires_fastapi
def test_the_report_page_shows_the_performance(db_path):
    _seed(db_path)
    _seed_snapshots(db_path)

    html = _client(db_path).get("/report").text

    assert "最大回撤" in html
    assert "25.00%" in html
    assert "4 条快照" in html


@requires_fastapi
def test_the_report_page_explains_why_a_metric_is_missing(db_path):
    """快照不足时说清「为什么」，而不是印一个 0.00% 让用户以为是结论。"""
    _seed(db_path)

    html = _client(db_path).get("/report").text

    assert "快照不足" in html
    assert "holdings snapshot" in html


@requires_fastapi
def test_the_report_page_lists_the_allocation(db_path):
    _seed(db_path)

    html = _client(db_path).get("/report").text

    assert "资产配置占比" in html
    assert "stock" in html
    assert "100.00%" in html


# ------------------------------------------------------------------ 曲线页


@requires_fastapi
@requires_plotly
def test_the_chart_page_embeds_the_figure(db_path):
    _seed_snapshots(db_path)

    response = _client(db_path).get("/chart")

    assert response.status_code == 200
    assert "plotly" in response.text
    assert "<div" in response.text


@requires_fastapi
def test_the_chart_page_explains_a_missing_plotly(monkeypatch, db_path):
    """缺 plotly 是用户当场能处置的状态，收成页面上的提示而不是 500。"""
    monkeypatch.setitem(sys.modules, "plotly", None)
    monkeypatch.setitem(sys.modules, "plotly.graph_objects", None)
    _seed_snapshots(db_path)

    response = _client(db_path).get("/chart")

    assert response.status_code == 200
    assert "holdings-cli[chart]" in response.text


@requires_fastapi
def test_the_chart_page_explains_an_empty_range(db_path):
    """没有任何快照时给出去哪儿补数据，而不是一张空图——空图像「净值跌没了」。"""
    response = _client(db_path).get("/chart")

    assert response.status_code == 200
    assert "holdings snapshot" in response.text


@requires_fastapi
def test_a_bad_start_date_is_a_sentence_not_a_json_422(db_path):
    """日期写错时用户该看到一句人话，而不是浏览器里一段 `{"detail":[...]}`。"""
    _seed_snapshots(db_path)

    response = _client(db_path).get("/chart", params={"start": "去年"})

    assert response.status_code == 200
    assert "不是合法日期" in response.text
    assert "YYYY-MM-DD" in response.text
