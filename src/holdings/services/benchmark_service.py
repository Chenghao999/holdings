"""基准对比服务（B-39）：把组合的时间加权收益与指数收益摆在一起。

这是唯一同时碰 `storage` + `data` + `portfolio` 的地方，分工是：
`storage` 给快照与缓存的指数序列，`data` 在缓存不新鲜时去取数，
`portfolio.metrics` 做两边的收益率计算。

**这一层最重要的约定是「宁可显示 `—`，不给一个错的数」**（沿用
`report_service` 的规矩）：手记快照条数少、间隔不规律、基准序列可能缺某一天，
凡是口径不成立的情形一律返回 `None`，由渲染层显示 `—`。判断依据都写在下面。

整件事的意义在现金流上：快照的 `total_value` 里混着入金 / 出金，直接与指数比，
**一笔入金会被算成「跑赢」**——数字看着完全正常，却是错的。所以组合一侧走
逐段剔除现金流的 TWR，而不是首尾相除。
"""

from __future__ import annotations

from bisect import bisect_right
from datetime import date, timedelta
from itertools import pairwise

from holdings.data import history
from holdings.data.fetcher import SymbolNotFoundError
from holdings.data.resilience import DEFAULT_TIMEOUT_SECONDS, call_with_timeout
from holdings.exceptions import RecordNotFoundError
from holdings.models.benchmark import BenchmarkResult
from holdings.portfolio import metrics
from holdings.storage import price_history_dao, snapshot_dao

#: 口径句。放在 service 层——「收益是怎么算的」是口径决定，不是排版。
BENCHMARK_METHOD_NOTE = (
    "口径：组合收益为时间加权（TWR），逐段剔除快照上记的净入金"
    "（没记 --flow 即视为该段没有出入金）；基准按同一批快照日接链，"
    "非交易日取该日之前最近的收盘价"
)

#: 取指数序列时往前多取的天数。**必须留这一段**：首条快照常落在周末，
#: 而它对应的收盘价在**它之前**那个交易日；窗口从快照当天起，那个价就在窗外，
#: 对齐会判成「找不到」——一条本可以算出来的对比被一个周末卡掉。
#: 复用 DAO 的同一个常数，免得「取数窗口」与「缓存算不算盖住」两处各写一个数。
_LOOKBACK_DAYS = price_history_dao.RANGE_SLACK_DAYS


def get_benchmark(
    db_path: str,
    against: str,
    start: date | None = None,
    ttl_seconds: int = 86400,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> BenchmarkResult:
    """算组合与基准的同期收益，不输出任何文字。

    `--against` 认不出时抛 `SymbolNotFoundError`（exit 2）——**不退化成
    「随便挑一个市场去问」**：那会把「我不认识这个词」混成「网络取不到」
    （exit 1），用户照着错的方向去查网络、重装依赖（B-36 是同一类）。
    """
    ref = history.resolve_against(against)
    if ref is None:
        raise SymbolNotFoundError(
            f"认不出这是哪个市场的基准：{against}；"
            "可写 沪深300 / 中证500 / 上证指数 / 标普500 / 纳斯达克，"
            "或 6 位 A 股指数代码、^GSPC 这类美股代码"
        )

    snaps = snapshot_dao.get_all(db_path)
    if not snaps:
        # 空库是**正常状态**（还没开始记），不是错误——与 `holdings snapshots`
        # 的空库提示一致，所以 exit 0 带一句提示，不抛异常。
        # 这一条**必须排在建 `selected` 之前**：空库配上 `--start` 时，
        # 下面那句报错文案要引用首末快照日期，空列表上会 IndexError——
        # 一个「用户还没记过快照」被报成崩溃。
        return BenchmarkResult(
            against=ref.label,
            snapshot_count=0,
            notes=["还没有任何快照，先执行 holdings snapshot 记录一份"],
        )

    selected = [s for s in snaps if start is None or s.snapshot_date >= start]
    if not selected:
        # 有快照、但 `--start` 把它们全筛掉了：这是**用户给的值有问题**，
        # 照 `chart_service` 的先例报出来，并把现有的时间范围带上，
        # 用户才知道该把 `--start` 调到哪里。
        raise RecordNotFoundError(_empty_message(snaps, start))

    if len(selected) < 2:
        return BenchmarkResult(
            against=ref.label,
            snapshot_count=len(selected),
            first_date=selected[0].snapshot_date,
            last_date=selected[0].snapshot_date,
            notes=["至少要 2 条快照才能对比；再记一条 holdings snapshot 之后即可"],
        )

    first = selected[0].snapshot_date
    last = selected[-1].snapshot_date
    levels = _benchmark_levels(db_path, ref, first, last, ttl_seconds, timeout_seconds)
    dates = [day for day, _close in levels]

    paired = [(snap, _close_on_or_before(levels, dates, snap.snapshot_date)) for snap in selected]
    matched = [(snap, close) for snap, close in paired if close is not None]

    notes = [BENCHMARK_METHOD_NOTE]
    missing = [snap.snapshot_date for snap, close in paired if close is None]
    if missing:
        notes.append(
            "基准序列里没有 "
            + "、".join(str(day) for day in missing)
            + " 或之前最近的收盘价，这些点已从两侧同时剔除"
            "（只剔一侧会让两条链错位）"
        )

    if len(matched) < 2:
        notes.append("可对齐的快照不足 2 条，组合 / 基准 / 超额均不可计算")
        return BenchmarkResult(
            against=ref.label,
            snapshot_count=len(selected),
            first_date=first,
            last_date=last,
            notes=notes,
        )

    values = [snap.total_value for snap, _close in matched]
    flows = [snap.external_flow for snap, _close in matched]
    portfolio_return = metrics.time_weighted_return(values, flows)
    if portfolio_return is None:
        notes.append("组合收益算不出来（每一段的上一期净值都 ≤ 0，或某段的净入金大于期末净值）")

    index_levels = [close for _snap, close in matched]
    benchmark_return: float | None = None
    if all(level > 0 for level in index_levels):
        benchmark_return = metrics.chain_link(
            [curr / prev - 1 for prev, curr in pairwise(index_levels)]
        )
    else:
        notes.append("基准序列里有非正的收盘价，基准收益无法计算")

    # 超额要两个数都在才有意义：任何一侧是 `—` 时，相减得到的不是「超额」，
    # 而是把一侧的缺失伪装成一个具体的数——那正是本模块开头要防的事。
    excess = (
        portfolio_return - benchmark_return
        if portfolio_return is not None and benchmark_return is not None
        else None
    )

    return BenchmarkResult(
        against=ref.label,
        snapshot_count=len(selected),
        portfolio_return=portfolio_return,
        benchmark_return=benchmark_return,
        excess_return=excess,
        first_date=first,
        last_date=last,
        notes=notes,
    )


def _benchmark_levels(
    db_path: str,
    ref: history.BenchmarkRef,
    first: date,
    last: date,
    ttl_seconds: int,
    timeout_seconds: float,
) -> list[tuple[date, float]]:
    """基准的收盘价序列：先看缓存，不新鲜才取数。

    **取完一律回读缓存**，不管刚才是命中还是现取的。两条路走同一个出口，
    「缓存里的」与「刚取回来的」就不可能长得不一样——否则测试覆盖的是一条路，
    用户跑的是另一条。

    取不到时 `call_with_timeout` / `fetch_history` 抛
    `DataSourceUnavailableError`（exit 1），**不返回空列表假装成功**：
    空序列会一路走到对齐那一步，最后的表现是「找不到收盘价」，
    与真正的原因（网络取不到）隔了好几层。
    """
    fetch_start = first - timedelta(days=_LOOKBACK_DAYS)
    if not price_history_dao.is_fresh(db_path, ref.symbol, fetch_start, last, ttl_seconds):
        got = call_with_timeout(
            history.fetch_history,
            timeout_seconds,
            ref.symbol,
            ref.market,
            fetch_start,
            last,
        )
        price_history_dao.upsert_many(db_path, ref.symbol, got.rows, got.source)
    return price_history_dao.get_range(db_path, ref.symbol, fetch_start, last)


def _close_on_or_before(
    levels: list[tuple[date, float]], dates: list[date], day: date
) -> float | None:
    """序列里 ≤ `day` 的最近一个交易日的收盘价；一条都没有时返回 `None`。

    快照是用户手记的，多半落在周末或节假日，那一天没有收盘价，取**它之前**
    最近一个交易日的——这正是「按快照日对齐」的落地方式。
    """
    index = bisect_right(dates, day) - 1
    return levels[index][1] if index >= 0 else None


def _empty_message(snaps: list, start: date | None) -> str:
    """照 `chart_service._empty_message` 的文案：报错要带出现有的时间范围。"""
    if not snaps:
        return "还没有任何快照，先执行 holdings snapshot 记录一份"
    return (
        f"{start} 之后没有快照（现有 {len(snaps)} 条，"
        f"{snaps[0].snapshot_date} ~ {snaps[-1].snapshot_date}）；"
        f"请调整 --start 或先执行 holdings snapshot"
    )
