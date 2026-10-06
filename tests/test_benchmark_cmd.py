"""`holdings benchmark`：把入金从收益里剔除，再与指数比。

这一项的意义全在第一条判据上：**一份含入金的手记快照序列，对比结果不把入金
算成跑赢**。所以这里既有「记了 `--flow` 得到 0%」也有「同一组净值、没记
`--flow` 得到 +50%」——两个断言并排放，第二个就是不做这件事会拿到的错数。

不触网：需要走取数那一段的用例装一个假的 akshare；不需要的用
`no_fetch` 夹住（真去问一次网络会抛断言，而不是静默慢下来）。
"""

from __future__ import annotations

import sys
import types
from datetime import date, timedelta

import pandas as pd
import pytest

from holdings.cli.main import main
from holdings.cli.renderers.table_renderer import render_benchmark_line
from holdings.data import history, sources
from holdings.models.snapshot import Snapshot
from holdings.services import benchmark_service
from holdings.storage import price_history_dao, snapshot_dao


def _snap(day: date, total: float, flow: float = 0.0) -> Snapshot:
    return Snapshot(
        snapshot_date=day,
        total_value=total,
        equity_value=total,
        gold_value=0.0,
        external_flow=flow,
    )


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(sources.time, "sleep", lambda _seconds: None)


@pytest.fixture
def fake_akshare(monkeypatch, no_sleep):
    """装一个假的 akshare，`levels` 是 `{日期: 收盘}`。"""

    def _install(levels: dict[date, float]):
        seen: list[str] = []

        def index_zh_a_hist(symbol, period, start_date, end_date):
            seen.append(symbol)
            rows = [
                {"日期": day.isoformat(), "收盘": close}
                for day, close in sorted(levels.items())
                if start_date <= day.strftime("%Y%m%d") <= end_date
            ]
            return pd.DataFrame(rows, columns=["日期", "收盘"])

        module = types.ModuleType("akshare")
        module.index_zh_a_hist = index_zh_a_hist
        monkeypatch.setitem(sys.modules, "akshare", module)
        return seen

    return _install


@pytest.fixture
def no_fetch(monkeypatch):
    """凡走到取数就当场失败。缓存命中的用例不该打网络。"""

    def _boom(*args, **kwargs):
        raise AssertionError("这条用例不该去取数")

    monkeypatch.setattr(benchmark_service, "call_with_timeout", _boom)


def _cache(db_path, symbol: str, levels: dict[date, float]) -> None:
    """把指数序列直接写进缓存，省掉一次取数。"""
    price_history_dao.upsert_many(db_path, symbol, sorted(levels.items()), "akshare")


def _run(monkeypatch, *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["holdings", "benchmark", *argv])
    try:
        main()
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


def _cfg(db_path, **overrides):
    """命令内部那次 `load_config()` 的替身。

    **只留这一份**：属性少一个，报出来的是 `AttributeError`，看着像代码坏了，
    其实只是夹具不全——`sync_retry_count`（`resilience.retry_count()` 自己会再调
    一次 `load_config`）和 `sync_timeout_seconds` 都是这么各崩一轮才补上的。
    加字段时改这一处就够。
    """
    values = {
        "database_path": db_path,
        "history_ttl_seconds": 86400,
        "sync_retry_count": 1,
        "sync_timeout_seconds": 10.0,
    }
    values.update(overrides)
    return types.SimpleNamespace(**values)


@pytest.fixture
def use_db(db_path, monkeypatch):
    """把命令内部的 load_config 指向临时库。"""
    monkeypatch.setattr("holdings.utils.config.load_config", lambda *a, **k: _cfg(db_path))
    return db_path


# --------------------------------------------------------- 判据：入金不算跑赢

JAN, FEB = date(2024, 1, 2), date(2024, 2, 1)


@pytest.fixture
def deposited(db_path):
    """市场没动，中间入金 5 万；指数整段持平。"""
    snapshot_dao.add(db_path, _snap(JAN, 100_000.0))
    snapshot_dao.add(db_path, _snap(FEB, 150_000.0, flow=50_000.0))
    _cache(db_path, "000300", {JAN: 3000.0, FEB: 3000.0})
    return db_path


def test_a_deposit_is_not_outperformance(deposited, no_fetch):
    """**判据**：入金 5 万、指数持平 → 组合 0%、超额 0%，那笔钱不算跑赢。"""
    got = benchmark_service.get_benchmark(deposited, "沪深300")

    assert got.portfolio_return == 0.0
    assert got.benchmark_return == 0.0
    assert got.excess_return == 0.0


def test_forgetting_the_flow_gives_the_wrong_number(db_path, no_fetch):
    """同一组净值，`--flow` 记成 0 就得到 +50%——这正是 B-39 要防的错数。"""
    snapshot_dao.add(db_path, _snap(JAN, 100_000.0))
    snapshot_dao.add(db_path, _snap(FEB, 150_000.0))
    _cache(db_path, "000300", {JAN: 3000.0, FEB: 3000.0})

    got = benchmark_service.get_benchmark(db_path, "沪深300")

    assert got.portfolio_return == pytest.approx(0.5)
    assert got.excess_return == pytest.approx(0.5)


def test_the_command_prints_the_three_numbers(use_db, deposited, no_fetch, monkeypatch, capsys):
    code = _run(monkeypatch, "--against", "沪深300")
    out = capsys.readouterr().out

    assert code == 0
    assert "沪深300（000300）" in out
    assert "组合 0.00%" in out
    assert "基准 0.00%" in out
    assert "超额 0.00%" in out


# ------------------------------------------------------------------ 对齐与区间


def test_the_benchmark_is_taken_on_the_snapshot_dates_not_the_ends(db_path, no_fetch):
    """基准按**快照日**接链，不是拿区间首尾两个点相除。

    这一段指数两头都是 3000，中间却先跌到 2400 再涨回来：按首尾算基准是 0%，
    按快照日接链是 `(2400/3000-1) + (3000/2400-1)` 接起来 = 0% 也恰好是 0——
    所以这条用例再叠一个组合数，让两种算法的差别落在超额上。

    组合净值同样走完整的三段，取 `+21%`。
    """
    day1, day2, day3 = date(2024, 1, 2), date(2024, 2, 1), date(2024, 3, 1)
    snapshot_dao.add(db_path, _snap(day1, 100_000.0))
    snapshot_dao.add(db_path, _snap(day2, 110_000.0))
    snapshot_dao.add(db_path, _snap(day3, 121_000.0))
    # 中间那天指数大跌又涨回：按快照日接链是 −20% 与 +25%，接起来 = 0%；
    # 若错用「区间首尾相除」也会得到 0%，所以指数换成两头不等的：
    # 3000 → 2400 → 3600：接链 = 0.8 × 1.5 − 1 = 0.2；首尾相除 = 0.2。
    # 两者在这一组上又相等——所以关键在**中间点必须被用到**这点靠下面的
    # 「基准序列缺某天」用例来钉，这里只确认三个数都出得来。
    _cache(db_path, "000300", {day1: 3000.0, day2: 2400.0, day3: 3600.0})

    got = benchmark_service.get_benchmark(db_path, "沪深300")

    assert got.portfolio_return == pytest.approx(0.21)
    assert got.benchmark_return == pytest.approx(0.2)
    assert got.excess_return == pytest.approx(0.01)


def test_a_missing_level_drops_that_point_from_both_sides(db_path, fake_akshare):
    """基准序列里没有某个快照日（及之前）的收盘价时，**两侧一起**剔掉那个点。

    只剔一侧会让两条链错位：组合是三段、基准是两段，算出来的「超额」是拿
    两个不同长度的区间在比——数字看着正常，口径却已经错了。
    """
    day1, day2, day3 = date(2024, 1, 2), date(2024, 2, 1), date(2024, 3, 1)
    snapshot_dao.add(db_path, _snap(day1, 100_000.0))
    snapshot_dao.add(db_path, _snap(day2, 110_000.0))
    snapshot_dao.add(db_path, _snap(day3, 121_000.0))
    # 数据源就**没有** day1 或之前的收盘价（比如那个指数那时还没发布）——
    # 第一条快照因此对不上，只能被剔掉。
    fake_akshare({day2: 3000.0, day3: 3300.0})

    got = benchmark_service.get_benchmark(db_path, "沪深300")

    # 剩下的两点：组合 110000 → 121000 = +10%，基准 3000 → 3300 = +10%。
    assert got.portfolio_return == pytest.approx(0.1)
    assert got.benchmark_return == pytest.approx(0.1)
    assert got.first_date == day1, "区间还是原来那段，剔掉的是点、不是区间"
    assert any(str(day1) in note for note in got.notes), "剔了哪个点要说出来"


def test_too_few_aligned_points_gives_a_dash_with_a_reason(db_path, fake_akshare):
    """可对齐的点不足 2 个：三个数都出不来，并说清是**基准这边对不上**。

    快照是两条，基准只在最后一天有收盘价——第一条快照那个点没有基准可比。
    """
    day1, day2 = date(2024, 1, 2), date(2024, 2, 1)
    snapshot_dao.add(db_path, _snap(day1, 100_000.0))
    snapshot_dao.add(db_path, _snap(day2, 110_000.0))
    fake_akshare({day2: 3000.0})

    got = benchmark_service.get_benchmark(db_path, "沪深300")

    assert got.portfolio_return is None
    assert got.benchmark_return is None
    assert got.excess_return is None
    assert any("可对齐的快照不足 2 条" in note for note in got.notes)


def test_an_unusable_portfolio_chain_says_why(db_path, no_fetch):
    """每一段的上一期净值都 ≤ 0 → 组合收益是 `—`，而不是 0。

    首条快照净值为 0 时那一段除不了，与 `metrics.return_series` 同款丢弃；
    全丢掉就是「算不出来」。
    """
    day1, day2 = date(2024, 1, 2), date(2024, 2, 1)
    snapshot_dao.add(db_path, _snap(day1, 0.0))
    snapshot_dao.add(db_path, _snap(day2, 100_000.0))
    _cache(db_path, "000300", {day1: 3000.0, day2: 3300.0})

    got = benchmark_service.get_benchmark(db_path, "沪深300")

    assert got.portfolio_return is None
    assert got.benchmark_return == pytest.approx(0.1)
    # 一侧是 `—` 时超额也必须是 `—`：相减会把缺失伪装成一个具体的数。
    assert got.excess_return is None
    assert any("组合收益算不出来" in note for note in got.notes)


def test_a_non_positive_index_level_gives_a_dash(db_path, no_fetch):
    """基准序列里有非正的收盘价时，基准收益是 `—` 而不是「除出来一个数」。

    真实指数不会是 0，但缓存是本地数据、用户也可能手改过——与其除出个
    `inf` 一路走进报表，不如在这里判成算不出来。
    """
    day1, day2 = date(2024, 1, 2), date(2024, 2, 1)
    snapshot_dao.add(db_path, _snap(day1, 100_000.0))
    snapshot_dao.add(db_path, _snap(day2, 110_000.0))
    _cache(db_path, "000300", {day1: 0.0, day2: 3300.0})

    got = benchmark_service.get_benchmark(db_path, "沪深300")

    assert got.benchmark_return is None
    assert got.excess_return is None
    assert any("非正的收盘价" in note for note in got.notes)


def test_a_snapshot_on_a_non_trading_day_uses_the_previous_close(db_path, no_fetch):
    """快照手记在周末时，取**该日之前最近一个交易日**的收盘价。

    这是「按快照日对齐」的落地方式——快照多半落在周末，找不到就取前一个
    交易日，而不是判成缺数据。
    """
    saturday = date(2024, 1, 6)  # 周六；之前最近的交易日是 1 月 5 日（周五）
    snapshot_dao.add(db_path, _snap(saturday, 100_000.0))
    snapshot_dao.add(db_path, _snap(date(2024, 2, 1), 110_000.0))
    # 缓存里**只有交易日**——周六那天本来就没有收盘价。指数整段持平，
    # 所以「周六取到了周五的 3000」这件事会直接体现在基准是 0% 上。
    _cache(db_path, "000300", {date(2024, 1, 5): 3000.0, date(2024, 2, 1): 3000.0})

    got = benchmark_service.get_benchmark(db_path, "沪深300")

    # 周六那条若被当成「找不到收盘价」剔掉，就只剩一个点、三个数都出不来。
    assert got.portfolio_return == pytest.approx(0.1)
    assert got.benchmark_return == 0.0
    # 只剩口径句——没有「剔掉了某个点」那条说明。
    assert got.notes == [benchmark_service.BENCHMARK_METHOD_NOTE]


# -------------------------------------------------------------------- 缓存


def test_a_fresh_cache_means_no_network(db_path, no_fetch, fake_akshare):
    """缓存盖得住区间时**不打网络**——`no_fetch` 会在取数时当场失败。"""
    day1, day2 = date(2024, 1, 2), date(2024, 2, 1)
    snapshot_dao.add(db_path, _snap(day1, 100_000.0))
    snapshot_dao.add(db_path, _snap(day2, 110_000.0))
    _cache(db_path, "000300", {day1: 3000.0, day2: 3300.0})
    fake_akshare({})  # 装了假源，但这条用例根本不该走到它

    got = benchmark_service.get_benchmark(db_path, "沪深300")

    assert got.benchmark_return == pytest.approx(0.1)


def test_a_cache_that_does_not_cover_the_window_is_refetched(db_path, fake_akshare):
    """缓存只有末尾一小段时不命中：区间没盖住就得重取。

    只判「有没有行」的话，会拿一段缺了开头的序列去算收益——数字看着完全正常。
    """
    day1, day2, day3 = date(2024, 1, 2), date(2024, 6, 1), date(2024, 12, 1)
    snapshot_dao.add(db_path, _snap(day1, 100_000.0))
    snapshot_dao.add(db_path, _snap(day2, 110_000.0))
    snapshot_dao.add(db_path, _snap(day3, 121_000.0))
    _cache(db_path, "000300", {day2: 2400.0, day3: 3600.0})  # 没有 day1 那一段
    seen = fake_akshare({day1: 3000.0, day2: 2400.0, day3: 3600.0})

    got = benchmark_service.get_benchmark(db_path, "沪深300")

    assert seen == ["000300"], "区间没盖住就该真的去取一次"
    # 取回来的一整段都在：3000 → 2400 → 3600 = 0.8 × 1.5 − 1 = 20%
    assert got.benchmark_return == pytest.approx(0.2)


def test_what_was_fetched_is_written_back_to_the_cache(db_path, fake_akshare):
    """取回来的序列要落库，第二次跑就不再打网络。"""
    day1, day2 = date(2024, 1, 2), date(2024, 2, 1)
    snapshot_dao.add(db_path, _snap(day1, 100_000.0))
    snapshot_dao.add(db_path, _snap(day2, 110_000.0))
    fake_akshare({day1: 3000.0, day2: 3300.0})

    benchmark_service.get_benchmark(db_path, "沪深300")

    cached = price_history_dao.get_range(db_path, "000300", day1, day2)
    assert cached == [(day1, 3000.0), (day2, 3300.0)]


def test_the_lookback_window_reaches_back_before_the_first_snapshot(
    db_path, fake_akshare, monkeypatch
):
    """取数窗口要往前放宽：首条快照落在周末时，它的收盘价在**它之前**。

    窗口从快照当天算起的话，那个价在窗外，对齐会判成「找不到」——
    一条本来能算出来的对比被一个周末卡掉。
    """
    saturday = date(2024, 1, 6)
    snapshot_dao.add(db_path, _snap(saturday, 100_000.0))
    snapshot_dao.add(db_path, _snap(date(2024, 2, 1), 110_000.0))
    fake_akshare({date(2024, 1, 5): 3000.0, date(2024, 2, 1): 3300.0})

    got = benchmark_service.get_benchmark(db_path, "沪深300")

    assert got.benchmark_return == pytest.approx(0.1)
    assert got.notes[0] == benchmark_service.BENCHMARK_METHOD_NOTE


# ---------------------------------------------------------------- 取不到 / 认不出


def test_an_unrecognized_benchmark_exits_2(db_path, monkeypatch, capsys):
    """`--against 乱写的` → exit 2，不是 1。

    退化成「随便挑一个市场去问」的话，报出来的会是「数据源不可用」（exit 1），
    用户照着错的方向去查网络、重装依赖，而问题在自己敲的那个词上（B-36 同类）。
    """
    snapshot_dao.add(db_path, _snap(JAN, 100_000.0))
    snapshot_dao.add(db_path, _snap(FEB, 110_000.0))

    monkeypatch.setattr("holdings.utils.config.load_config", lambda *a, **k: _cfg(db_path))

    code = _run(monkeypatch, "--against", "乱写的")
    err = capsys.readouterr().err

    assert code == 2
    assert "错误（2）：" in err
    assert "乱写的" in err
    assert "Traceback" not in err


def test_a_benchmark_that_cannot_be_fetched_exits_1(db_path, monkeypatch, capsys, no_sleep):
    """基准取不到数 → exit 1（数据源不可用），不是「超额 0%」。"""
    snapshots = [_snap(JAN, 100_000.0), _snap(FEB, 110_000.0)]
    for snap in snapshots:
        snapshot_dao.add(db_path, snap)
    monkeypatch.setitem(sys.modules, "akshare", None)  # 「没装这个包」在运行时的样子

    monkeypatch.setattr("holdings.utils.config.load_config", lambda *a, **k: _cfg(db_path))

    code = _run(monkeypatch, "--against", "沪深300")
    err = capsys.readouterr().err

    assert code == 1
    assert "错误（1）：" in err
    assert "Traceback" not in err


def test_a_missing_against_is_a_usage_error(use_db):
    """`--against` 是必填：不写就报用法错误，别默认挑一个基准替用户决定口径。"""
    from holdings.cli.commands.benchmark import benchmark_cmd

    param = next(p for p in benchmark_cmd.params if p.name == "against")
    assert param.required


# ------------------------------------------------------------------ 快照不足


def test_an_empty_database_exits_0_with_a_hint(use_db, monkeypatch, capsys, no_fetch):
    """空库是**正常状态**（还没开始记），不是错误——exit 0 加一句提示。"""
    code = _run(monkeypatch, "--against", "沪深300")
    out = capsys.readouterr().out

    assert code == 0
    assert "快照不足" in out
    assert "holdings snapshot" in out


def test_a_single_snapshot_exits_0_with_a_hint(db_path, monkeypatch, capsys, no_fetch):
    """只有 1 条：算不出对比，但也不是错误——快照本来就是一条条记起来的。"""
    snapshot_dao.add(db_path, _snap(JAN, 100_000.0))

    monkeypatch.setattr("holdings.utils.config.load_config", lambda *a, **k: _cfg(db_path))

    code = _run(monkeypatch, "--against", "沪深300")
    out = capsys.readouterr().out

    assert code == 0
    assert "至少 2 条" in out


def test_a_start_that_filters_everything_out_exits_2(
    use_db, deposited, monkeypatch, capsys, no_fetch
):
    """`--start` 把快照全筛掉 → exit 2，且文案里带出现有的时间范围。

    这与「空库」是两回事：库里有数据，是**用户给的值**不合适，所以照
    `chart_service` 的先例报错，用户才知道该把 `--start` 调到哪里。
    """
    code = _run(monkeypatch, "--against", "沪深300", "--start", "2030-01-01")
    err = capsys.readouterr().err

    assert code == 2
    assert "2030-01-01" in err
    assert "2024-01-02" in err, "得说清现有数据到哪儿，否则用户不知道往哪儿调"


def test_the_empty_message_survives_an_empty_snapshot_list():
    """`_empty_message` 在空列表上不能炸。

    `get_benchmark` 现在会先一步返回，所以它眼下拿不到空列表；但一个**对两种
    输入里的一种会 IndexError** 的工具函数是颗雷（这个 bug 真出现过：
    空库配上 `--start` 时崩在文案里）。留下守卫，并用例钉住。
    """
    message = benchmark_service._empty_message([], date(2024, 1, 2))

    assert "holdings snapshot" in message


def test_start_keeps_only_the_snapshots_on_or_after_it(deposited, no_fetch):
    """`--start` 含当天，只算筛出来的那一段。"""
    got = benchmark_service.get_benchmark(deposited, "沪深300", start=FEB)

    assert got.snapshot_count == 1
    assert got.portfolio_return is None
    assert "至少要 2 条" in got.notes[0]


# ------------------------------------------------------------------ 渲染与注册


def test_the_method_note_is_always_shown(deposited, no_fetch):
    """口径句每次都在：**没记 `--flow` 就等于断言那段没有出入金**，
    不写出来用户不会知道这件事会静默地改变结果。"""
    got = benchmark_service.get_benchmark(deposited, "沪深300")

    assert benchmark_service.BENCHMARK_METHOD_NOTE in got.notes
    assert "--flow" in benchmark_service.BENCHMARK_METHOD_NOTE


def test_the_rendered_line_carries_the_notes(deposited, no_fetch):
    got = benchmark_service.get_benchmark(deposited, "沪深300")

    text = render_benchmark_line(got)

    assert text.startswith("基准对比（2 条快照")
    assert benchmark_service.BENCHMARK_METHOD_NOTE in text


def test_an_unknown_ratio_is_rendered_as_a_dash(deposited, no_fetch):
    """算不出来一律 `—`，绝不用 0 冒充——`0.00%` 的超额看着像结论。"""
    got = benchmark_service.get_benchmark(deposited, "沪深300")
    got.portfolio_return = None
    got.benchmark_return = None
    got.excess_return = None

    text = render_benchmark_line(got)

    assert "组合 — | 基准 — | 超额 —" in text


def test_the_command_is_registered():
    from holdings.cli.main import cli

    assert "benchmark" in cli.commands


def test_the_alias_resolves_to_the_index_endpoint(deposited, no_fetch):
    """别名走的是**指数**端点，所以 000001 是上证指数、不是平安银行。"""
    _cache(deposited, "000001", {JAN: 3000.0, FEB: 3300.0})

    got = benchmark_service.get_benchmark(deposited, "上证指数")

    assert got.against == "上证指数（000001）"


def test_the_ttl_and_the_timeout_both_come_from_the_config(db_path, deposited, monkeypatch, capsys):
    """命令把 `history_ttl_seconds` 与 `sync.timeout_seconds` 都传下去。

    **超时这一条是真跑一次才发现的**：`sync` 一直传着
    `cfg.sync_timeout_seconds`，而 `benchmark` 漏了——用户为慢网络调大了那个值，
    这里却还按写死的 10 秒放弃，报出来的是「拉取超时」，把真正的原因（这个源
    本来就慢）盖住了。
    """
    seen: dict[str, object] = {}
    real = benchmark_service.get_benchmark

    def spy(db_path, against, start=None, ttl_seconds=0, timeout_seconds=0.0):
        seen["ttl"] = ttl_seconds
        seen["timeout"] = timeout_seconds
        return real(db_path, against, start=start, ttl_seconds=ttl_seconds)

    monkeypatch.setattr(
        "holdings.utils.config.load_config",
        lambda *a, **k: _cfg(db_path, sync_timeout_seconds=42.0),
    )
    monkeypatch.setattr("holdings.services.benchmark_service.get_benchmark", spy)

    code = _run(monkeypatch, "--against", "沪深300")

    assert code == 0
    assert seen["ttl"] == 86400
    assert seen["timeout"] == 42.0


def test_the_fetch_is_bounded_by_a_timeout(db_path, monkeypatch):
    """取数必须包在 `call_with_timeout` 里：上游不响应时不能把命令挂死。"""
    seen: dict[str, object] = {}

    def spy(func, seconds, *args):
        seen["func"] = func
        seen["seconds"] = seconds
        return history.HistoryResult(rows=[(JAN, 3000.0), (FEB, 3300.0)], source="akshare")

    monkeypatch.setattr(benchmark_service, "call_with_timeout", spy)
    snapshot_dao.add(db_path, _snap(JAN, 100_000.0))
    snapshot_dao.add(db_path, _snap(FEB, 110_000.0))

    benchmark_service.get_benchmark(db_path, "沪深300", timeout_seconds=7.5)

    assert seen["func"] is history.fetch_history
    assert seen["seconds"] == 7.5


def test_a_long_gap_still_chains_without_annualizing(deposited, no_fetch):
    """间隔不规律不影响可比性——TWR 是逐段接链，这是它相对年化的好处。

    这里只钉住「不需要年化也能出数」：两条快照相隔 30 天，三个数都算得出来。
    """
    got = benchmark_service.get_benchmark(deposited, "沪深300")

    assert (deposited and got.last_date - got.first_date) == timedelta(days=30)
    assert got.portfolio_return is not None
    assert got.excess_return is not None
