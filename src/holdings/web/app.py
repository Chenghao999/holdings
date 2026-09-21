"""holdings 的 Web 看板：持仓 / 报表 / 净值曲线三页，**只读**。

数据全部来自 `services/`——一行 SQL、一个网络请求都没有。页面里的每个数都由
服务层算好、`utils/formatter.py` 格式化好，这里只负责拼成 HTML：口径归服务层、
排版归模板，中间不夹第三套判断。

**这一版刻意只读**。`add` / `meta` 这些写操作不在这里：写入闸门（[B-11]）要把
校验结果连同「哪一条不合法、为什么」一起搬进页面才算数，而一个绕开闸门的
Web 表单正好是那种「多了个入口就少了一道校验」的坏例子。先把读的做扎实。

FastAPI / uvicorn / jinja2 是可选依赖（`pip install 'holdings[web]'`），
本模块只在真正启动看板时导入。

[B-11]: ../../../docs/BACKLOG.md#b-11
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from holdings.exceptions import HoldingsError
from holdings.services import asset_meta_service
from holdings.services.chart_service import networth_figure
from holdings.services.portfolio_service import (
    HOLDINGS_COLUMNS,
    foreign_hint,
    get_summary,
    holdings_cell,
    unpriced_hint,
)
from holdings.services.report_service import get_performance
from holdings.utils.formatter import (
    UNKNOWN,
    format_money,
    format_number,
    format_percent,
    format_ratio,
)

TEMPLATES = Jinja2Templates(directory=Path(__file__).parent / "templates")

#: 左对齐的列。其余都是数——数右对齐，位数才对得齐，一眼能比出大小。
_TEXT_COLUMNS = {"symbol", "name", "market", "asset_type"}


def _columns() -> list[dict]:
    """表头：标签取自服务层那份列契约，这里只补一个对齐方式。"""
    return [
        {"label": label, "numeric": key not in _TEXT_COLUMNS}
        for key, label in HOLDINGS_COLUMNS.items()
    ]


def create_app(db_path: str) -> FastAPI:
    """构造看板应用。`db_path` 在启动时定死，页面本身不改任何东西。"""
    # docs_url / redoc_url 关掉：`/docs` 是 FastAPI 自动生成的接口文档，
    # 而这个应用没有 REST 接口给谁调用，挂在那里只会让人以为它是个 API 服务。
    app = FastAPI(title="holdings", docs_url=None, redoc_url=None)

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request) -> HTMLResponse:
        """持仓汇总：卡片 + 持仓表 + 「哪些没算进来」的提示。"""
        summary = get_summary(db_path)
        return TEMPLATES.TemplateResponse(
            request,
            "index.html",
            {
                "cards": _cards(summary),
                "columns": _columns(),
                # 单元格文本由服务层给，与 TUI 同一份实现——两个界面显示的是
                # 同一张表，不该各自决定「成本价留几位小数」。
                "rows": [
                    [holdings_cell(column, row) for column in HOLDINGS_COLUMNS]
                    for _, row in summary.holdings_df.iterrows()
                ],
                "hints": [hint for hint in (unpriced_hint(summary), foreign_hint(summary)) if hint],
            },
        )

    @app.get("/report", response_class=HTMLResponse)
    def report(request: Request) -> HTMLResponse:
        """报表：绩效指标 + 资产配置 + 费用分项，即 `report --verbose` 的那一份。"""
        summary = get_summary(db_path)
        performance = get_performance(db_path)
        symbols = [] if summary.holdings_df.empty else summary.holdings_df["symbol"].tolist()
        return TEMPLATES.TemplateResponse(
            request,
            "report.html",
            {
                "performance": _performance(performance),
                "fee_rate": asset_meta_service.fee_rate_total(db_path, symbols),
                "allocation": [
                    {"label": atype, "value": format_ratio(ratio)}
                    for atype, ratio in summary.allocation.items()
                ],
                "fees": [
                    {"label": symbol, "value": format_money(amount)}
                    for symbol, amount in summary.fee_breakdown.items()
                ],
            },
        )

    @app.get("/chart", response_class=HTMLResponse)
    def chart(request: Request, start: str | None = None) -> HTMLResponse:
        """净值曲线。`start` 是 `YYYY-MM-DD`，筛出该日（含）之后的点。

        `start` 收成字符串而不是 `date`：声明成 `date` 时 FastAPI 会在参数不合法
        时直接返回一坨 JSON 422——对一个 HTML 页面来说，用户看到的是浏览器里
        一段没有上下文的 `{"detail":[...]}`。这里自己解析，好把话说明白。
        """
        parsed, error = _parse_start(start)
        figure_html, chart_error = (None, error) if error else _figure_html(db_path, parsed)
        return TEMPLATES.TemplateResponse(
            request,
            "chart.html",
            {
                "start": start or "",
                "figure": figure_html,
                # 缺 plotly、还没有快照、日期筛空了——三件事的处置完全不同，
                # 服务层给的文案已经把该做什么说清楚了，照原样显示即可。
                "error": chart_error,
            },
        )

    return app


def _parse_start(raw: str | None) -> tuple[date | None, str | None]:
    """解析 `?start=`。返回（日期, 错误文案），两者必有其一为 None。"""
    if not raw:
        return None, None
    try:
        return date.fromisoformat(raw), None
    except ValueError:
        return None, f"「{raw}」不是合法日期，请按 YYYY-MM-DD 填写（例如 2025-01-01）"


def _figure_html(db_path: str, start: date | None) -> tuple[str | None, str | None]:
    """净值曲线的 HTML 片段，以及取不到图时的说明。

    这里把 `HoldingsError` 收成页面上的提示而不是让请求 500：缺 plotly 与
    「这段时间没有快照」都是用户当场能处理的状态，用错误页盖住反而要多绕一圈
    才知道该怎么办。异常文案由服务层给，与 CLI 的 `chart` 命令一字不差。
    """
    try:
        figure = networth_figure(db_path, start=start)
    except HoldingsError as exc:
        return None, str(exc)
    # include_plotlyjs="cdn"：把 plotly.js 从 CDN 引进来，而不是每打开一次页面
    # 就内联 3MB 的脚本。代价是看这一页要联网——本地看板可以接受，
    # 需要离线可看时用 `holdings chart` 导出独立文件。
    return figure.to_html(full_html=False, include_plotlyjs="cdn"), None


def _cards(summary) -> list[dict]:
    """顶部四张卡片。算不出来时显示 `—`（service 给的就是 `None`）。"""
    profit = summary.total_profit
    return [
        {"label": "总市值", "value": format_money(summary.total_value)},
        {"label": "总成本", "value": format_money(summary.total_cost)},
        {
            "label": "总盈亏",
            "value": format_money(profit),
            # 只有算得出盈亏时才带盈亏率：`— (—)` 是两遍废话。
            "sub": UNKNOWN if profit is None else format_percent(summary.profit_rate),
            "tone": _tone(profit),
        },
        {"label": "累计费用", "value": format_money(summary.total_fees)},
    ]


def _tone(profit: float | None) -> str:
    """盈亏的颜色档：红涨绿跌（A 股的习惯），算不出来时不上色。

    颜色只是锦上添花，金额本身已经把话说完了——所以 `—` 不上色，
    而不是给它一个「中性」的灰色假装它也是个结果。
    """
    if profit is None or profit == 0:
        return ""
    return "gain" if profit > 0 else "loss"


def _performance(performance) -> dict:
    """绩效块。快照不足与「口径不成立」都照服务层给的 notes 显示。"""
    if performance.snapshot_count < 2:
        return {
            "ready": False,
            "message": (
                f"快照不足（当前 {performance.snapshot_count} 条，至少 2 条），"
                f"回撤 / 年化 / 夏普均不可计算；先执行 holdings snapshot 记录一份"
            ),
        }
    return {
        "ready": True,
        "span": f"{performance.first_date} ~ {performance.last_date}",
        "count": performance.snapshot_count,
        # 键名不叫 items：Jinja 取 `performance.items` 会拿到 dict 自带的
        # `.items` 方法，模板里就成了「对函数做 for」，报的是看不懂的 TypeError。
        "metrics": [
            {"label": "最大回撤", "value": format_ratio(performance.max_drawdown)},
            {"label": "年化收益", "value": format_ratio(performance.annualized_return)},
            {"label": "夏普比率", "value": format_number(performance.sharpe)},
        ],
        "notes": performance.notes,
    }
