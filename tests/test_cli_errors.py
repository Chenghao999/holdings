"""CLI 退出码契约测试。

这些用例锁住的是 pyproject.toml 的入口点必须指向 `main` 这件事：
一旦改回裸 click group `cli`，异常映射层就被绕开，
下面每一条都会退化成「裸 traceback + 退出码 1」。

`main()` 内部走 `cli.main(standalone_mode=False)`，所以这里直接给 sys.argv 打桩调用，
而不是用 CliRunner——CliRunner 会绕过 main()，测不到映射层。
"""

from __future__ import annotations

import importlib
import sys
from importlib import metadata

import pytest

import holdings
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


def test_version_is_the_packaged_one(tmp_path, monkeypatch, capsys):
    """`--version` 与 `holdings.__version__` 说的必须是同一个版本号。

    版本号此前在 `pyproject.toml` 与 `holdings/__init__.py` 各手写一份，发布时
    要记得改两处——漏一处不会有任何东西会响。现改为单一来源（打包元数据），
    这条用例锁住它：谁再写回一个字面值，两边就对不上。
    """
    monkeypatch.chdir(tmp_path)

    assert run_main(monkeypatch, "--version") == 0
    packaged = metadata.version("holdings-cli")
    assert packaged in capsys.readouterr().out
    assert holdings.__version__ == packaged


def test_the_version_falls_back_when_the_package_is_not_installed(monkeypatch):
    """查不到元数据时 `import holdings` 本身不能失败。

    源码树里直接 import 就是这种情形（`pytest` 的 `pythonpath = ["src"]`），
    而 import 抛异常会让每条命令都退化成裸 traceback——正是 B-08 修掉的那类问题。
    """

    def _missing(name: str) -> str:
        raise metadata.PackageNotFoundError(name)

    monkeypatch.setattr(metadata, "version", _missing)
    try:
        assert importlib.reload(holdings).__version__ == "0.0.0+unknown"
    finally:
        monkeypatch.undo()
        importlib.reload(holdings)


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
    assert "holdings-cli[data]" in err, "安装提示里的方括号要原样出现，不能被 Rich 吃掉"


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


def _write_import_csv(tmp_path, *rows: str):
    """写一份导入用的 CSV（表头 + 给定行），返回路径。"""
    header = "symbol,market,trade_date,trade_type,quantity,price\n"
    csv_file = tmp_path / "trades.csv"
    csv_file.write_text(header + "".join(f"{r}\n" for r in rows), encoding="utf-8")
    return csv_file


def test_import_of_unposted_rows_exits_0_by_default(tmp_path, monkeypatch, capsys):
    """认得出但不入账的行不是错误：默认退出码仍是 0，靠汇总行告诉用户。

    （`--strict` 才把它升级成失败，见下一条。）
    """
    monkeypatch.chdir(tmp_path)
    csv_file = _write_import_csv(
        tmp_path,
        "600519,A股,2025-01-02,BUY,100,10",
        "600519,A股,2025-06-20,分红派息,0,0",
    )

    code = run_main(monkeypatch, "import", "--file", str(csv_file))

    assert code == 0
    out = capsys.readouterr().out
    assert "识别 2 行，入账 1 笔，未入账 1 行" in out
    assert "第 3 行 分红派息，未入账" in out


def test_import_with_unposted_rows_exits_5_under_strict(tmp_path, monkeypatch, capsys):
    """`--strict` 是 B-27 定下的：有未入账的行就非零退出，且一笔都不写。

    非零而不是 0，是为了让脚本能判断「这份对账单有没有被完整导入」；
    一笔都不写，是因为 import 还没有幂等（BACKLOG B-29）——写了一半再以
    非零退出码结束，用户重跑一次就把账翻倍了。
    """
    from holdings.storage import transaction_dao

    monkeypatch.chdir(tmp_path)
    csv_file = _write_import_csv(
        tmp_path,
        "600519,A股,2025-01-02,BUY,100,10",
        "600519,A股,2025-06-20,分红派息,0,0",
    )

    code = run_main(monkeypatch, "import", "--file", str(csv_file), "--strict")

    assert code == 5
    assert "错误（5）" in capsys.readouterr().err
    assert transaction_dao.get_all(str(tmp_path / "data" / "holdings.db")) == []


def test_import_of_an_unknown_trade_type_exits_5(tmp_path, monkeypatch, capsys):
    """认不出的取值与「认识但不入账」区别对待：前者整批拒绝。

    这一条锁的是 B-27 划的那条界——不能为了「让对账单导得进来」，
    把认不出的值也当成不入账放过。
    """
    from holdings.storage import transaction_dao

    monkeypatch.chdir(tmp_path)
    csv_file = _write_import_csv(
        tmp_path,
        "600519,A股,2025-01-02,BUY,100,10",
        "600519,A股,2025-06-20,HODL,0,0",
    )

    code = run_main(monkeypatch, "import", "--file", str(csv_file))

    assert code == 5
    assert "不是合法交易类型" in capsys.readouterr().err
    assert transaction_dao.get_all(str(tmp_path / "data" / "holdings.db")) == []


def test_import_of_an_unrecognized_format_exits_5(tmp_path, monkeypatch, capsys):
    """认不出对账单的格式时，退出码 5 且一笔都不写。

    这一条锁的是 B-28 的判据：格式陌生时**不猜**。猜一个最像的也能跑到底，
    但那意味着整批数字可能是错的，而用户会以为导成功了。
    """
    from holdings.storage import transaction_dao

    monkeypatch.chdir(tmp_path)
    stranger = tmp_path / "stranger.csv"
    stranger.write_text(
        "交易日期,证券编码,摘要,股数,单价\n2025-01-02,600519,买入,100,10\n", encoding="utf-8"
    )

    code = run_main(monkeypatch, "import", "--file", str(stranger))

    assert code == 5
    assert "错误（5）：" in capsys.readouterr().err
    assert transaction_dao.get_all(str(tmp_path / "data" / "holdings.db")) == []


def test_a_gb18030_statement_imports(tmp_path, monkeypatch, capsys):
    """GBK 的对账单要能直接读，不能要求用户先去转一次码。

    Windows 上 Excel 另存为 CSV 默认就是 GBK——这是最常拿到的那种文件。
    """
    monkeypatch.chdir(tmp_path)
    statement = tmp_path / "gbk.csv"
    statement.write_bytes(
        (
            "成交日期,证券代码,业务名称,成交数量,成交均价,佣金,印花税,过户费,交易市场\n"
            "2025-01-02,600519,证券买入,100,1500.00,5.00,0.00,0.10,上海\n"
        ).encode("gb18030")
    )

    code = run_main(monkeypatch, "import", "--file", str(statement))

    assert code == 0
    assert "识别 1 行，入账 1 笔，未入账 0 行" in capsys.readouterr().out
