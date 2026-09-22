"""`holdings chart --start`：从空参数变成真的能筛。

`--start` 的 help 此前自己就写着「暂存参数」，`networth_figure()` 也没有对应
形参——传了完全不生效，而 USER_GUIDE 却拿它当日期筛选的示例。
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date

import pytest

from holdings.cli.main import main
from holdings.models.snapshot import Snapshot
from holdings.services import chart_service
from holdings.storage import snapshot_dao


def _snap(month: int, total: float) -> Snapshot:
    return Snapshot(
        snapshot_date=date(2025, month, 1),
        total_value=total,
        equity_value=total,
        gold_value=0.0,
    )


@pytest.fixture
def seeded(db_path):
    for month, total in ((1, 100.0), (2, 120.0), (3, 90.0), (4, 110.0)):
        snapshot_dao.add(db_path, _snap(month, total))
    return db_path


@pytest.fixture
def use_db(seeded, monkeypatch):
    """把命令内部的 load_config 指向那个**已经有快照**的临时库。"""

    class _Cfg:
        database_path = seeded

    monkeypatch.setattr("holdings.utils.config.load_config", lambda *a, **k: _Cfg())
    return seeded


def _run(monkeypatch, *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["holdings", "chart", *argv])
    try:
        main()
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


# ------------------------------------------------------------------ 取数层


def test_without_start_every_snapshot_is_drawn(seeded):
    dates, values = chart_service.networth_series(seeded)

    assert len(dates) == 4
    assert values == [100.0, 120.0, 90.0, 110.0]


def test_start_keeps_only_the_snapshots_on_or_after_it(seeded):
    """判据里的 `--start 2025-01-01` 只含该日期之后的点——含当天。"""
    dates, _ = chart_service.networth_series(seeded, start=date(2025, 3, 1))

    assert dates == [date(2025, 3, 1), date(2025, 4, 1)]


def test_start_on_an_existing_date_includes_that_date(seeded):
    """「该日之后」含当天，否则用户按记得的日期筛会少一条。"""
    dates, _ = chart_service.networth_series(seeded, start=date(2025, 2, 1))

    assert dates[0] == date(2025, 2, 1)


def test_a_future_start_is_an_error_not_an_empty_chart(seeded):
    """BACKLOG B-04 的判据：未来日期要给出明确提示，而不是一张空白图。

    空图与「净值跌没了」在图上分不出来，所以宁可不生成。
    """
    from holdings.exceptions import RecordNotFoundError

    with pytest.raises(RecordNotFoundError) as exc:
        chart_service.networth_series(seeded, start=date(2030, 1, 1))

    message = str(exc.value)
    assert "2030-01-01" in message
    # 提示里要有实际的数据范围，用户才知道该把 --start 调到哪里
    assert "2025-01-01" in message
    assert "2025-04-01" in message


def test_no_snapshots_at_all_says_how_to_start(db_path):
    from holdings.exceptions import RecordNotFoundError

    with pytest.raises(RecordNotFoundError, match="holdings snapshot"):
        chart_service.networth_series(db_path)


# ------------------------------------------------------------------ 命令层


def test_future_start_exits_2_without_writing_a_file(use_db, monkeypatch, capsys, tmp_path):
    """未来日期：说清原因、退出码 2、**不写出空白 HTML**。"""
    out_file = tmp_path / "networth.html"

    code = _run(monkeypatch, "--start", "2030-01-01", "--output", str(out_file))
    err = capsys.readouterr().err

    assert code == 2
    assert "错误（2）：" in err
    assert "2030-01-01" in err
    assert not out_file.exists(), "空白图比没有图更糟"


def test_malformed_start_exits_5_without_a_traceback(use_db, monkeypatch, capsys):
    """判据：`--start 2025-13-45` 退出码 5，输出 `错误（5）：…`，无 traceback。"""
    code = _run(monkeypatch, "--start", "2025-13-45")
    err = capsys.readouterr().err

    assert code == 5
    assert "错误（5）：" in err
    assert "2025-13-45" in err
    assert "Traceback" not in err


def test_start_help_no_longer_says_it_is_a_placeholder():
    """help 文案别再说「暂存参数」——它现在真的生效了。"""
    from holdings.cli.commands.chart import chart_cmd

    help_text = next(p.help for p in chart_cmd.params if p.name == "start")

    assert "暂存" not in help_text
    assert "YYYY-MM-DD" in help_text


# ------------------------------------------------------------------ 产图路径

requires_plotly = pytest.mark.skipif(
    importlib.util.find_spec("plotly") is None,
    reason="需要 plotly（chart extra；CI 的 test 作业装的是 .[dev,chart]）",
)


@requires_plotly
def test_the_chart_is_written_and_the_browser_is_asked_to_open_it(
    use_db, monkeypatch, capsys, tmp_path
):
    """成功路径：图真的写出来了、告诉用户写到哪儿、并请浏览器打开。

    这条此前完全没有。上面四条覆盖的都是**图该不该产**（未来日期、非法日期）
    与**数据算得对不对**（`chart_service`），而「算完之后落盘并告知用户」那段
    ——`chart.py` 最后三行——在测试里从没执行过。于是 plotly 换了
    `write_html` 的签名、输出路径处理错了、或者干脆忘了通知用户，
    CI 都不会红，用户敲一下才知道。

    `webbrowser.open` 必须打桩：不打桩时本地跑一次测试就弹一个浏览器窗口，
    在 CI 上则是一个没人看、也没人发现失败的副作用。
    """
    out_file = tmp_path / "networth.html"
    opened: list[str] = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url) or True)

    code = _run(monkeypatch, "--output", str(out_file))
    out = capsys.readouterr().out

    assert code == 0
    html = out_file.read_text(encoding="utf-8")
    # 「是个 plotly 图」而不是「建出来就空着的文件」——退出码 0 只说明没抛异常
    assert "Plotly.newPlot" in html
    # 快照日期要真的进到图里：只断言「文件非空」的话，一张空图也能过
    assert "2025-01-01" in html
    assert "已生成图表" in out
    assert str(out_file) in out, "得说清写到哪儿了，否则用户还得自己去找文件"
    assert opened == [str(out_file)], "没请浏览器打开，这一步就白写了"
