"""图表服务：准备净值曲线数据，返回 plotly Figure 或 JSON。"""

from __future__ import annotations

from datetime import date
from typing import Any

from holdings.exceptions import RecordNotFoundError
from holdings.storage import snapshot_dao


def networth_series(db_path: str, start: date | None = None) -> tuple[list[date], list[float]]:
    """筛出用于画图的快照日期与净值。

    `start` 只保留该日期（含）之后的快照。筛完一条不剩时抛 `RecordNotFoundError`，
    而不是返回一张空图——**空图看起来像「净值跌没了」**，而事实是这段时间没有
    数据，两件事在图上分不出来。报错文案里带上现有的时间范围，用户才知道该把
    `--start` 调到哪里。

    这一步不依赖 plotly，因此即使没装画图库，数据问题也能先报出来。
    """
    snaps = snapshot_dao.get_all(db_path)
    selected = [s for s in snaps if start is None or s.snapshot_date >= start]
    if not selected:
        raise RecordNotFoundError(_empty_message(snaps, start))
    return [s.snapshot_date for s in selected], [s.total_value for s in selected]


def _empty_message(snaps, start: date | None) -> str:
    if not snaps:
        return "还没有任何快照，先执行 holdings snapshot 记录一份"
    return (
        f"{start} 之后没有快照（现有 {len(snaps)} 条，"
        f"{snaps[0].snapshot_date} ~ {snaps[-1].snapshot_date}）；"
        f"请调整 --start 或先执行 holdings snapshot"
    )


def networth_figure(db_path: str, start: date | None = None) -> Any:
    """根据快照生成净值曲线 Figure（plotly 懒加载）。

    先取数据再导入 plotly：数据为空是用户自己库里的状态、当场就能处理，
    而缺依赖要装包，两件事都成立时先说前者更有用。
    """
    dates, values = networth_series(db_path, start)

    try:
        import plotly.graph_objects as go  # 懒加载
    except ImportError as exc:
        # 此前抛裸 RuntimeError：绕过 main() 的退出码映射，用户看到 traceback。
        from holdings.exceptions import MissingDependencyError

        raise MissingDependencyError(
            "未安装 plotly，无法生成图表；请运行 pip install 'holdings-cli[chart]'"
        ) from exc

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=values, mode="lines+markers", name="总资产"))
    fig.update_layout(title="资产净值曲线", xaxis_title="日期", yaxis_title="净值")
    return fig
