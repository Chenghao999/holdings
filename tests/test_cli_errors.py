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

from holdings.cli.main import exit_code_for, main
from holdings.exceptions import (
    ConfigError,
    DatabaseError,
    DataSourceUnavailableError,
    HoldingsError,
    MissingDependencyError,
    RecordNotFoundError,
    SymbolNotFoundError,
    TradeValidationError,
)


@pytest.mark.parametrize(
    ("exc_type", "expected"),
    [
        (DataSourceUnavailableError, 1),
        (SymbolNotFoundError, 2),
        (RecordNotFoundError, 2),
        (ConfigError, 3),
        (DatabaseError, 4),
        (TradeValidationError, 5),
        (MissingDependencyError, 6),
    ],
)
def test_the_exit_code_mapping_covers_every_exception(exc_type, expected):
    """映射表本身就是契约，直接断言它，而不是「跑一遍看退出码」。

    这张表此前藏在 main() 的函数体里，用例只能断言「返回值在 1~5 之间」——
    一个漏掉的分支不会被任何用例发现。
    """
    assert issubclass(exc_type, HoldingsError)
    assert exit_code_for(exc_type()) == expected


def test_an_unmapped_holdings_error_defaults_to_1():
    """将来新增异常却忘了进映射表时，落到 1 而不是 0——不能静默成功。"""

    class _BrandNewError(HoldingsError):
        pass

    assert exit_code_for(_BrandNewError()) == 1


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


def test_remove_of_a_missing_record_exits_2_with_the_prefix(tmp_path, monkeypatch, capsys):
    """BACKLOG B-08 的判据：`remove --id 99999` 输出 `错误（2）：…` 且退出码 2。

    此前它输出裸文本「未找到交易 #3」再 exit(2)：退出码是对的，但文案绕过了
    统一前缀，按 `错误（N）：` 匹配的脚本会漏掉这一条。
    """
    monkeypatch.chdir(tmp_path)

    code = run_main(monkeypatch, "remove", "--id", "99999")
    err = capsys.readouterr().err

    assert code == 2
    assert "错误（2）：" in err
    assert "未找到交易 #99999" in err


def test_sync_failing_entirely_exits_1_with_the_prefix(tmp_path, monkeypatch, capsys):
    """全部标的同步失败同样走统一前缀——此前是自己 SystemExit(1)。"""
    from datetime import date

    from holdings.data.fetcher import DataSourceUnavailableError
    from holdings.models.enums import AssetType, MarketType, TradeType
    from holdings.models.transaction import Transaction
    from holdings.services import sync_service
    from holdings.storage import transaction_dao

    monkeypatch.chdir(tmp_path)
    db = tmp_path / "data" / "holdings.db"
    transaction_dao.add(
        str(db),
        Transaction(
            symbol="600519",
            market=MarketType.A_SHARE,
            asset_type=AssetType.STOCK,
            trade_date=date(2025, 1, 1),
            trade_type=TradeType.BUY,
            quantity=100.0,
            price=10.0,
        ),
    )

    def _boom(symbol, market):
        raise DataSourceUnavailableError("网络不通")

    monkeypatch.setattr(sync_service.fetcher, "fetch_price", _boom)

    code = run_main(monkeypatch, "sync", "--market", "A股")
    err = capsys.readouterr().err

    assert code == 1
    assert "错误（1）：" in err
    assert "全部同步失败" in err
    assert "holdings[data]" in err, "安装提示里的方括号要原样出现，不能被 Rich 吃掉"


def test_command_bodies_do_not_raise_systemexit():
    """结构性守卫：退出码只由 `main()` 的映射层决定。

    命令体里自己 `SystemExit(N)` 会绕过映射层——退出码或许还对，但文案绕过
    统一前缀，而且新增分支时没人拦着。这条用例把「不再出现」变成可执行的约定。
    """
    import ast
    import pathlib

    from holdings.cli import commands

    def _mentions_systemexit(path: pathlib.Path) -> bool:
        """用 AST 判断，不做文本匹配。

        注释里出现 `SystemExit` 是正常的（要解释为什么不再用它），
        文本匹配会把解释也当成违反。ast 天然不含注释。
        """
        tree = ast.parse(path.read_text(encoding="utf-8"))
        return any(
            isinstance(node, ast.Name) and node.id == "SystemExit" for node in ast.walk(tree)
        )

    offenders = [
        path.name
        for path in sorted(pathlib.Path(commands.__file__).parent.glob("*.py"))
        if _mentions_systemexit(path)
    ]

    assert offenders == [], f"这些命令文件里还有 SystemExit：{offenders}"


def test_remove_deletes_the_record_after_confirmation(tmp_path, monkeypatch, capsys):
    """B-11 换了调用路径（改经 trade_service），行为必须不变。"""
    from datetime import date

    import click

    from holdings.models.enums import AssetType, MarketType, TradeType
    from holdings.models.transaction import Transaction
    from holdings.storage import transaction_dao

    monkeypatch.chdir(tmp_path)
    db = tmp_path / "data" / "holdings.db"
    tx_id = transaction_dao.add(
        str(db),
        Transaction(
            symbol="600519",
            market=MarketType.A_SHARE,
            asset_type=AssetType.STOCK,
            trade_date=date(2025, 1, 1),
            trade_type=TradeType.BUY,
            quantity=100.0,
            price=10.0,
        ),
    )
    monkeypatch.setattr(click, "confirm", lambda *a, **k: True)

    code = run_main(monkeypatch, "remove", "--id", str(tx_id))

    assert code == 0
    assert "已删除交易" in capsys.readouterr().out
    assert transaction_dao.get(str(db), tx_id) is None


def test_declining_the_confirmation_aborts_with_130(tmp_path, monkeypatch, capsys):
    from datetime import date

    import click

    from holdings.models.enums import AssetType, MarketType, TradeType
    from holdings.models.transaction import Transaction
    from holdings.storage import transaction_dao

    monkeypatch.chdir(tmp_path)
    db = tmp_path / "data" / "holdings.db"
    tx_id = transaction_dao.add(
        str(db),
        Transaction(
            symbol="600519",
            market=MarketType.A_SHARE,
            asset_type=AssetType.STOCK,
            trade_date=date(2025, 1, 1),
            trade_type=TradeType.BUY,
            quantity=100.0,
            price=10.0,
        ),
    )
    monkeypatch.setattr(click, "confirm", lambda *a, **k: False)

    code = run_main(monkeypatch, "remove", "--id", str(tx_id))

    assert code == 0
    assert "已取消" in capsys.readouterr().out
    assert transaction_dao.get(str(db), tx_id) is not None, "拒绝确认时不能删"
