"""`holdings meta`：标的名称与年化管理费率的录入。

`asset_meta` 表此前只有建表语句、全项目零引用——SCHEMA.md 写着「完整支持
基金托管费」，却没有任何入口能填。
"""

from __future__ import annotations

import sys

import pytest

from holdings.cli.main import main
from holdings.services import asset_meta_service


@pytest.fixture
def use_db(tmp_path, monkeypatch):
    """一个 config.yaml 指向临时库的项目目录。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text("database_path: holdings.db\n", encoding="utf-8")
    return str(tmp_path / "holdings.db")


def _run(monkeypatch, *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["holdings", "meta", *argv])
    try:
        main()
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


# ------------------------------------------------------------------ 录入


def test_records_name_and_fee_rate(use_db, monkeypatch, capsys):
    """BACKLOG B-01 的判据里的那条命令。"""
    code = _run(monkeypatch, "--symbol", "518880", "--name", "黄金ETF", "--fee-rate", "0.5")

    assert code == 0
    meta = asset_meta_service.get(use_db, "518880")
    assert meta.name == "黄金ETF"
    assert meta.annual_management_fee == 0.5
    assert meta.currency == "CNY", "不给币种时用默认值"


def test_the_output_says_the_rate_is_not_counted(use_db, monkeypatch, capsys):
    """费率不参与成本这件事必须写在用户看得见的地方，不能只写在文档里。"""
    _run(monkeypatch, "--symbol", "518880", "--fee-rate", "0.5")

    out = capsys.readouterr().out
    assert "不参与成本计算" in out


def test_recording_twice_updates_in_place(use_db, monkeypatch):
    _run(monkeypatch, "--symbol", "518880", "--name", "旧名字", "--fee-rate", "0.5")
    _run(monkeypatch, "--symbol", "518880", "--name", "黄金ETF")

    meta = asset_meta_service.get(use_db, "518880")

    assert meta.name == "黄金ETF"
    assert meta.annual_management_fee == 0.5, "没给的字段保留原值，不该被清掉"


# ------------------------------------------------------------------ 查看


def test_without_any_field_it_shows_what_is_recorded(use_db, monkeypatch, capsys):
    """一个字段都不给 = 查一下，而不是写一条空记录把名称与费率清掉。"""
    _run(monkeypatch, "--symbol", "518880", "--name", "黄金ETF", "--fee-rate", "0.5")
    capsys.readouterr()

    _run(monkeypatch, "--symbol", "518880")
    out = capsys.readouterr().out

    assert "黄金ETF" in out
    assert asset_meta_service.get(use_db, "518880").name == "黄金ETF"


def test_a_symbol_without_a_record_says_so(use_db, monkeypatch, capsys):
    _run(monkeypatch, "--symbol", "000001")

    assert "还没有基础信息" in capsys.readouterr().out


# ------------------------------------------------------------------ 删除


def test_remove_deletes_the_record(use_db, monkeypatch, capsys):
    _run(monkeypatch, "--symbol", "518880", "--name", "黄金ETF")
    capsys.readouterr()

    code = _run(monkeypatch, "--symbol", "518880", "--remove")

    assert code == 0
    assert "已删除" in capsys.readouterr().out
    assert asset_meta_service.get(use_db, "518880") is None


def test_removing_something_that_is_not_there_is_not_an_error(use_db, monkeypatch, capsys):
    """重复删除不是错误——目标状态已经达成，报错只会让脚本难写。"""
    code = _run(monkeypatch, "--symbol", "518880", "--remove")

    assert code == 0
    assert "没有基础信息可删" in capsys.readouterr().out


# ------------------------------------------------------------------ 参数


def test_symbol_is_required(use_db, monkeypatch, capsys):
    code = _run(monkeypatch, "--name", "黄金ETF")

    assert code == 5
    assert "错误（5）：" in capsys.readouterr().err
