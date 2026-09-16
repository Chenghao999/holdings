"""`holdings check` 的报错格式与退出码。

三件事此前都不对：缺依赖时输出裸的 Rich 文本再 `SystemExit(1)`（绕过统一前缀），
而 `--json` 分支在检查缺依赖**之前**就 return——缺依赖时仍退出 0，
靠退出码判断的 CI 脚本会漏检。那是 B-08 里唯一会真正咬人的一条。
"""

from __future__ import annotations

import json
import sys

import pytest

from holdings.cli.main import main
from holdings.utils import deps


def _statuses(*, missing: bool) -> list[deps.PackageStatus]:
    return [
        deps.PackageStatus(
            import_name="click", package_name="click", installed=True, required=True, purpose="必需"
        ),
        deps.PackageStatus(
            import_name="yfinance",
            package_name="yfinance",
            installed=not missing,
            required=True,
            purpose="必需",
        ),
    ]


@pytest.fixture
def environment(monkeypatch):
    """按需伪造依赖环境；返回设置函数。"""

    def _set(*, missing: bool) -> None:
        monkeypatch.setattr(deps, "check_dependencies", lambda: _statuses(missing=missing))
        monkeypatch.setattr(deps, "missing_required", lambda: ["yfinance"] if missing else [])

    return _set


def _run(monkeypatch, *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["holdings", "check", *argv])
    try:
        main()
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


# ------------------------------------------------------------------ 文本模式


def test_all_present_exits_0(environment, monkeypatch, capsys):
    environment(missing=False)

    code = _run(monkeypatch)

    assert code == 0
    assert "必需依赖齐全" in capsys.readouterr().out


def test_missing_required_exits_6_with_the_prefix(environment, monkeypatch, capsys):
    """BACKLOG B-08 的判据：缺依赖时输出 `错误（N）：…`。

    N 取 6 而不是 1：缺依赖要装包，重试没有用，与「网络不通」是两种处置。
    """
    environment(missing=True)

    code = _run(monkeypatch)
    err = capsys.readouterr().err

    assert code == 6
    assert "错误（6）：" in err
    assert "yfinance" in err
    assert "pip install -e ." in err


# ------------------------------------------------------------------ JSON 模式


def test_json_reports_ok_true_and_exits_0(environment, monkeypatch, capsys):
    environment(missing=False)

    code = _run(monkeypatch, "--json")

    assert code == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_json_reports_ok_false_and_exits_6(environment, monkeypatch, capsys):
    """缺依赖时 JSON 模式**必须**返回非零。

    此前它 `return` 在检查之前，退出码恒为 0——管道消费方看不出任何异常。
    """
    environment(missing=True)

    code = _run(monkeypatch, "--json")
    payload = json.loads(capsys.readouterr().out)

    assert code == 6
    assert payload["ok"] is False
    assert payload["missing_required"] == ["yfinance"]


@pytest.mark.parametrize("missing", [False, True])
def test_both_modes_agree_on_the_exit_code(environment, monkeypatch, missing):
    """文本与 JSON 的退出码必须一致——不一致就等于契约不存在。"""
    environment(missing=missing)

    text_code = _run(monkeypatch)
    json_code = _run(monkeypatch, "--json")

    assert text_code == json_code


def test_json_stays_parseable_even_when_it_fails(environment, monkeypatch, capsys):
    """错误提示走 stderr，stdout 留下的仍是可解析的 JSON。"""
    environment(missing=True)

    _run(monkeypatch, "--json")
    captured = capsys.readouterr()

    assert json.loads(captured.out)["ok"] is False
    assert "错误（6）：" in captured.err
