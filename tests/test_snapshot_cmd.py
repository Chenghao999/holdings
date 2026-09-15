"""`holdings snapshot` 的备注要真的落库。

此前 `--note` 只在终端回显一句「已记录快照 #2（月度定投第12期）」，
备注根本没有入库：`snapshots` 表没有 `note` 列，模型没有该字段，
`snapshot_dao.add` 只插 5 列。用户被告知存下了，再去查却什么也没有。
"""

from __future__ import annotations

import sqlite3
import sys

import pytest

from holdings.cli.main import main
from holdings.storage import snapshot_dao


@pytest.fixture
def project(tmp_path, monkeypatch):
    """一个 config.yaml 指向临时库的项目目录，返回库路径。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text("database_path: holdings.db\n", encoding="utf-8")
    return str(tmp_path / "holdings.db")


def _run(monkeypatch, *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["holdings", *argv])
    try:
        main()
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


def test_note_is_persisted_and_readable(project, monkeypatch):
    """BACKLOG B-03 的判据：写 note → 读回一致。"""
    code = _run(monkeypatch, "snapshot", "--total", "158000", "--note", "月度定投第12期")

    assert code == 0
    got = snapshot_dao.get_all(project)
    assert len(got) == 1
    assert got[0].total_value == 158000.0
    assert got[0].note == "月度定投第12期"


def test_without_note_the_column_is_null(project, monkeypatch):
    """不传 `--note` 存 NULL 而不是空串。"""
    _run(monkeypatch, "snapshot", "--total", "158000")

    conn = sqlite3.connect(project)
    try:
        raw = conn.execute("SELECT note FROM snapshots").fetchone()[0]
    finally:
        conn.close()

    assert raw is None


def test_the_echo_still_shows_the_note(project, monkeypatch, capsys):
    """落库了，回显的话也要留着——两者是同一件事的两面，不该只剩一个。"""
    _run(monkeypatch, "snapshot", "--total", "158000", "--note", "月度定投第12期")

    assert "月度定投第12期" in capsys.readouterr().out


def test_snapshots_command_lists_the_note(project, monkeypatch, capsys):
    """备注落库之后要能看见——写进去读不出来，与丢数据只差一步。"""
    _run(monkeypatch, "snapshot", "--total", "158000", "--note", "月度定投第12期")
    _run(monkeypatch, "snapshot", "--total", "160000", "--date", "2025-02-01")

    code = _run(monkeypatch, "snapshots")
    out = capsys.readouterr().out

    assert code == 0
    assert "月度定投第12期" in out
    assert "158,000.00" in out
    assert "2025-02-01" in out


def test_snapshots_command_on_an_empty_database_says_how_to_start(project, monkeypatch, capsys):
    """空列表要给出下一步，而不是只印一张空表。"""
    code = _run(monkeypatch, "snapshots")

    assert code == 0
    assert "暂无快照" in capsys.readouterr().out
