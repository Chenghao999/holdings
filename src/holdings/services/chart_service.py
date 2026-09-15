"""图表服务：准备净值曲线数据，返回 plotly Figure 或 JSON。"""

from __future__ import annotations

from typing import Any

from holdings.storage import snapshot_dao


def networth_figure(db_path: str) -> Any:
    """根据快照生成净值曲线 Figure（plotly 懒加载）。"""
    try:
        import plotly.graph_objects as go  # 懒加载
    except ImportError as exc:
        # 此前抛裸 RuntimeError：绕过 main() 的退出码映射，用户看到 traceback。
        from holdings.exceptions import MissingDependencyError

        raise MissingDependencyError(
            "未安装 plotly，无法生成图表；请运行 pip install 'holdings[chart]'"
        ) from exc

    snaps = snapshot_dao.get_all(db_path)
    dates = [s.snapshot_date for s in snaps]
    values = [s.total_value for s in snaps]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=values, mode="lines+markers", name="总资产"))
    fig.update_layout(title="资产净值曲线", xaxis_title="日期", yaxis_title="净值")
    return fig


def networth_json(db_path: str) -> str:
    """返回净值数据的 JSON 字符串，供 GUI 渲染。"""
    import json

    from holdings.storage import snapshot_dao

    snaps = snapshot_dao.get_all(db_path)
    return json.dumps(
        [{"date": s.snapshot_date.isoformat(), "value": s.total_value} for s in snaps],
        ensure_ascii=False,
    )
