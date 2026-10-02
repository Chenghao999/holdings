"""`holdings group` 命令：组合的列出 / 改名 / 合并（BACKLOG B-21）。

组合此前只是个筛选标签——`add` / `import` / `list --group` 都认它，却没有
任何地方能看有哪些组合、改名或合并：名字写错一次就永久留在库里。

这份用例盯住两件事：列出来的数确实来自各组合自己的汇总（与 `list --group`
同源，不是另算一份），以及**改名之后旧名筛不到、新名筛得到**——后者是 B-21
写在清单里的完成判据。
"""

from __future__ import annotations

import sys

import pytest

from holdings.cli.main import main
from holdings.models.enums import MarketType
from holdings.storage import price_cache_dao, transaction_dao


@pytest.fixture
def project(tmp_path, monkeypatch):
    """一个 config.yaml 指向临时库的项目目录，返回库路径。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text("database_path: holdings.db\n", encoding="utf-8")
    return str(tmp_path / "holdings.db")


def _run(monkeypatch, *argv: str) -> int:
    """走真正的入口跑一条命令，返回退出码。

    退出码的映射在 `main()` 里，直接调 callback 验不到。
    """
    monkeypatch.setattr(sys, "argv", ["holdings", *argv])
    try:
        main()
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


def _two_priced_groups(project, make_tx) -> None:
    transaction_dao.add_many(
        project,
        [
            make_tx(symbol="600519", qty=100, price=10.0, group="主账户"),
            make_tx(symbol="000001", qty=500, price=2.0, group="打新"),
        ],
    )
    price_cache_dao.upsert(project, "600519", 12.0)
    price_cache_dao.upsert(project, "000001", 3.0)


# ------------------------------------------------------------------ group list


def test_group_list_renders_each_group_with_its_own_numbers(project, monkeypatch, capsys, make_tx):
    _two_priced_groups(project, make_tx)

    assert _run(monkeypatch, "group", "list") == 0

    out = capsys.readouterr().out
    assert "主账户" in out
    assert "打新" in out
    # 两个组合各自的市值，而不是同一个数印两遍。
    assert "1,200.00" in out
    assert "1,500.00" in out


def test_group_list_on_an_empty_db_says_so(project, monkeypatch, capsys):
    assert _run(monkeypatch, "group", "list") == 0

    assert "暂无组合" in capsys.readouterr().out


def test_group_list_prefixes_the_partial_hint_with_the_group_name(
    project, monkeypatch, capsys, make_tx
):
    """多组的提示排在表后，不带组合名就分不清哪句说的是哪一组。"""
    transaction_dao.add(project, make_tx(symbol="600519", group="打新"))

    _run(monkeypatch, "group", "list")

    out = capsys.readouterr().out
    assert "组合『打新』" in out
    assert "无行情" in out


# ------------------------------------------------------------ rename / merge


def test_rename_echoes_the_next_command(project, monkeypatch, capsys, make_tx):
    transaction_dao.add_many(
        project,
        [make_tx(symbol="AAA", group="旧账户"), make_tx(symbol="BBB", group="别的组合")],
    )

    assert _run(monkeypatch, "group", "rename", "旧账户", "新账户") == 0

    out = capsys.readouterr().out
    assert "1 笔交易" in out
    assert "holdings list --group 新账户" in out


def test_merge_echoes_the_next_command(project, monkeypatch, capsys, make_tx):
    transaction_dao.add_many(
        project,
        [make_tx(symbol="AAA", group="打新"), make_tx(symbol="BBB", group="主账户")],
    )

    assert _run(monkeypatch, "group", "merge", "打新", "主账户") == 0

    out = capsys.readouterr().out
    assert "holdings list --group 主账户" in out


def test_renaming_the_configured_default_group_warns_about_the_config(
    project, monkeypatch, capsys, make_tx
):
    """改名照做，但要说出来：之后 `add` 不带 --group 还会写到「默认」去。"""
    transaction_dao.add(project, make_tx(symbol="AAA", group="默认"))

    assert _run(monkeypatch, "group", "rename", "默认", "主账户") == 0

    assert "default_group" in capsys.readouterr().out


def test_renaming_another_group_says_nothing_about_the_config(
    project, monkeypatch, capsys, make_tx
):
    transaction_dao.add(project, make_tx(symbol="AAA", group="打新"))

    _run(monkeypatch, "group", "rename", "打新", "新股")

    assert "default_group" not in capsys.readouterr().out


def test_renaming_to_the_same_name_is_reported_as_a_no_op(project, monkeypatch, capsys, make_tx):
    transaction_dao.add(project, make_tx(symbol="AAA", group="打新"))

    assert _run(monkeypatch, "group", "rename", "打新", "打新") == 0

    assert "未做任何改动" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        pytest.param(("group", "rename", "不存在", "新的"), 2, id="改名：源不存在"),
        pytest.param(("group", "rename", "打新", "主账户"), 5, id="改名：撞上已存在的名字"),
        pytest.param(("group", "rename", "打新", "  "), 5, id="改名：空名"),
        pytest.param(("group", "merge", "打新", "不存在"), 2, id="合并：目标不存在"),
        pytest.param(("group", "merge", "打新", "打新"), 5, id="合并：源与目标相同"),
    ],
)
def test_group_commands_map_errors_to_exit_codes(project, monkeypatch, make_tx, argv, expected):
    transaction_dao.add_many(
        project,
        [make_tx(symbol="AAA", group="打新"), make_tx(symbol="BBB", group="主账户")],
    )

    assert _run(monkeypatch, *argv) == expected


# ------------------------------------------------------------------ 判据锁


def test_after_rename_the_new_name_selects_all_and_the_old_selects_none(
    project, monkeypatch, capsys, make_tx
):
    """B-21 的完成判据：改名后新旧名字的筛选行为符合预期。"""
    transaction_dao.add_many(
        project,
        [make_tx(symbol="AAA", group="旧账户"), make_tx(symbol="BBB", group="别的组合")],
    )

    assert _run(monkeypatch, "group", "rename", "旧账户", "新账户") == 0
    capsys.readouterr()

    # 库层：旧名一笔不剩，新名拿到原记录（且没有把别的组合也卷进来）。
    assert transaction_dao.get_all(project, group="旧账户") == []
    assert [t.symbol for t in transaction_dao.get_all(project, group="新账户")] == ["AAA"]
    assert [t.symbol for t in transaction_dao.get_all(project, group="别的组合")] == ["BBB"]

    # 命令层：旧名筛出空表，新名筛出标的。
    assert _run(monkeypatch, "list", "--group", "旧账户") == 0
    old_out = capsys.readouterr().out
    assert "暂无持仓" in old_out
    assert "AAA" not in old_out

    assert _run(monkeypatch, "list", "--group", "新账户") == 0
    assert "AAA" in capsys.readouterr().out


def test_group_list_shows_foreign_holdings_in_the_excluded_column(
    project, monkeypatch, capsys, make_tx
):
    """外币计价的标的也进不了汇总，成因与「没行情」不同，列里要分开写。"""
    transaction_dao.add(
        project, make_tx(symbol="AAPL", group="美股组合", market=MarketType.US_STOCK)
    )
    price_cache_dao.upsert(project, "AAPL", 200.0, currency="USD")

    _run(monkeypatch, "group", "list")

    out = capsys.readouterr().out
    assert "1 外币计价" in out
    assert "以美元计价" in out


def test_merging_the_configured_default_group_warns_about_the_config(
    project, monkeypatch, capsys, make_tx
):
    """并走默认组合与改它的名是同一件事：那条路之后还会写到旧名字上。"""
    transaction_dao.add_many(
        project,
        [make_tx(symbol="AAA", group="默认"), make_tx(symbol="BBB", group="主账户")],
    )

    assert _run(monkeypatch, "group", "merge", "默认", "主账户") == 0

    assert "default_group" in capsys.readouterr().out
