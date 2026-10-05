"""基准对比的结果模型（DTO）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class BenchmarkResult:
    """组合 / 基准 / 超额三个数，外加每一条 `—` 的原因。

    三个收益率都是 `None` 时表示「口径不成立」，渲染层显示 `—`，**不要当成 0**
    ——`0.00%` 的超额看着像结论，实际只是两条序列没能对齐，这两件事在报表上
    必须分得出来（与 `services/report_service.PerformanceSummary` 同一条规矩）。

    收益率都是小数（`0.10` 即 +10%），与 `metrics` 里其余函数一致，渲染层直接
    交给 `format_ratio`。

    为什么不是 pydantic：`models/` 下其余几个都是「数据库某一行」的映射，
    这个是**算出来的结果**，没有对应的表，形状照 `PerformanceSummary` 用 dataclass。
    """

    #: 给人看的基准写法，如 `沪深300（000300）`。
    against: str
    snapshot_count: int
    portfolio_return: float | None = None
    benchmark_return: float | None = None
    excess_return: float | None = None
    first_date: date | None = None
    last_date: date | None = None
    #: 口径句与每一条 `—` 的原因，渲染层直接展示。理由放在 service 层而不是
    #: 渲染层：「为什么这个数算不出来」是口径决定，跟着计算走才不会两边打架。
    notes: list[str] = field(default_factory=list)
