"""调用 plotly 输出 HTML 图表文件。"""

from __future__ import annotations


def write_html(figure, path: str) -> None:
    """将 plotly Figure 写入 HTML 文件。"""
    figure.write_html(path)
