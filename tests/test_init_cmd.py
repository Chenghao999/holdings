"""`holdings init` 的实际行为。

`init --dev` 此前的全部实现是一句 `click.echo("开发模式已启用（暂不创建额外
数据）")`——参数存在却什么都不做，用户会以为开发环境被配置好了（B-17）。
参数已删除，这里锁住两件事：`init` 真的建出库与配置，且 `--dev` 不再被接受。
"""

from __future__ import annotations

import sys

import pytest

from holdings.cli.main import main


def _run(monkeypatch, *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["holdings", "init", *argv])
    try:
        main()
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    """`init` 按相对路径落库与落配置，chdir 到临时目录，避免写进仓库。"""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_creates_db_and_config(workdir, monkeypatch, capsys):
    code = _run(monkeypatch)

    assert code == 0
    assert (workdir / "data" / "holdings.db").exists()
    assert (workdir / "config.yaml").exists()
    assert "已初始化数据库" in capsys.readouterr().out


def test_existing_config_is_kept(workdir, monkeypatch):
    """已有配置不被默认值覆盖——否则用户改过的配置会被 init 悄悄抹掉。"""
    (workdir / "config.yaml").write_text("default_group: 自定义\n", encoding="utf-8")

    assert _run(monkeypatch) == 0

    assert "自定义" in (workdir / "config.yaml").read_text(encoding="utf-8")


def test_removed_dev_flag_is_rejected(workdir, monkeypatch, capsys):
    """B-17 的判据：这个参数要么产生可观察的差异，要么不复存在。"""
    code = _run(monkeypatch, "--dev")
    err = capsys.readouterr().err

    assert code == 5
    assert "错误（5）：" in err
    assert "--dev" in err
