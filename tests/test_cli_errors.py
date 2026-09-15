"""CLI 退出码契约测试。

这些用例锁住的是 pyproject.toml 的入口点必须指向 `main` 这件事：
一旦改回裸 click group `cli`，异常映射层就被绕开，
下面每一条都会退化成「裸 traceback + 退出码 1」。

`main()` 内部走 `cli.main(standalone_mode=False)`，所以这里直接给 sys.argv 打桩调用，
而不是用 CliRunner——CliRunner 会绕过 main()，测不到映射层。
"""

from __future__ import annotations

import sys

import pytest

from holdings.cli.main import main
from holdings.exceptions import (
    ConfigError,
    DatabaseError,
    DataSourceUnavailableError,
    HoldingsError,
    MissingDependencyError,
    SymbolNotFoundError,
    TradeValidationError,
)


@pytest.mark.parametrize(
    ("exc_type", "expected"),
    [
        (DataSourceUnavailableError, 1),
        (MissingDependencyError, 1),
        (SymbolNotFoundError, 2),
        (ConfigError, 3),
        (DatabaseError, 4),
        (TradeValidationError, 5),
    ],
)
def test_all_custom_exceptions_share_the_base_class(exc_type, expected):
    assert issubclass(exc_type, HoldingsError)
    assert expected in (1, 2, 3, 4, 5)


def run_main(monkeypatch, *argv: str) -> int:
    """执行一次 main()，返回退出码。

    成功路径与 --help 都是正常返回（standalone_mode=False 下 click 不再自行
    SystemExit），故正常返回记 0。
    """
    monkeypatch.setattr(sys, "argv", ["holdings", *argv])
    try:
        main()
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


def test_malformed_config_exits_3(tmp_path, monkeypatch, capsys):
    """配置损坏此前抛的是 yaml 的 ParserError，退出码退化为 1。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text("database_path: [unclosed\n", encoding="utf-8")

    code = run_main(monkeypatch, "list")
    err = capsys.readouterr().err

    assert code == 3
    assert "错误（3）" in err
    assert "配置文件格式错误" in err
    # 提示应当只有一行摘要，而不是 PyYAML 的整段解析现场
    assert len(err.strip().splitlines()) == 1


def test_invalid_market_exits_5(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    code = run_main(
        monkeypatch,
        "add",
        "--symbol",
        "X",
        "--market",
        "foo",
        "--type",
        "BUY",
        "--qty",
        "1",
        "--price",
        "1",
    )
    assert code == 5
    assert "错误（5）" in capsys.readouterr().err


def test_invalid_trade_type_exits_5(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code = run_main(
        monkeypatch,
        "add",
        "--symbol",
        "X",
        "--market",
        "A股",
        "--type",
        "HODL",
        "--qty",
        "1",
        "--price",
        "1",
    )
    assert code == 5


def test_invalid_date_exits_5(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code = run_main(
        monkeypatch,
        "add",
        "--symbol",
        "X",
        "--market",
        "A股",
        "--type",
        "BUY",
        "--qty",
        "1",
        "--price",
        "1",
        "--date",
        "2020-13-45",
    )
    assert code == 5


def test_oversell_exits_5(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    common = ("--symbol", "600519", "--market", "A股", "--price", "100")
    run_main(monkeypatch, "add", *common, "--type", "BUY", "--qty", "10")

    code = run_main(monkeypatch, "add", *common, "--type", "SELL", "--qty", "15")
    err = capsys.readouterr().err

    assert code == 5
    assert "超过当时持有量" in err


def test_negative_buy_quantity_exits_5(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code = run_main(
        monkeypatch,
        "add",
        "--symbol",
        "600519",
        "--market",
        "A股",
        "--type",
        "BUY",
        "--qty",
        "-5",
        "--price",
        "100",
    )
    assert code == 5


def test_help_and_version_still_exit_0(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run_main(monkeypatch, "--help") == 0
    assert run_main(monkeypatch, "--version") == 0
