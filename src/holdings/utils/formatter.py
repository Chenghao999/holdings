"""金额 / 价格 / 百分比 / 数量的格式化，纯函数。

渲染层此前各写各的：``f"{x:,.2f}"``、``f"{x:.4f}"``、``f"{x:.2f}%"`` 散在表格与
绩效行里，还各自维护一份「空值显示什么」的判断。收在这里之后，
「一个数该怎么显示」只有一处定义。

本模块零内部依赖，也不 import 任何表现层库——它只做字符串。
"""

from __future__ import annotations

import math

#: 值缺失时统一显示这个，而不是 0——「回撤 0.00%」看着像结论，
#: 「—」才是「这条数据算不出来」的诚实写法。
UNKNOWN = "—"


def is_missing(value) -> bool:
    """没有值有两种长相：`None`，以及 pandas 把 `None` 存成的 `NaN`。"""
    return value is None or (isinstance(value, float) and math.isnan(value))


def format_money(value) -> str:
    """千分位金额，两位小数。"""
    return UNKNOWN if is_missing(value) else f"{value:,.2f}"


def format_price(value) -> str:
    """单价，四位小数。

    比金额多留两位：A 股 ETF 报价到厘（如 `4.852`），按两位小数显示会把
    不同成本价的持仓显示成同一个数。
    """
    return UNKNOWN if is_missing(value) else f"{value:.4f}"


def format_number(value) -> str:
    """普通数值，两位小数（如夏普比率）。"""
    return UNKNOWN if is_missing(value) else f"{value:.2f}"


def format_percent(value) -> str:
    """百分比。**入参已经是百分数**：`4.13` → `4.13%`。

    小数形式的比例要走 `format_ratio`——两种口径混进一个函数，
    迟早有人把 `0.25` 印成「0.25%」。
    """
    return UNKNOWN if is_missing(value) else f"{value:.2f}%"


def format_ratio(value) -> str:
    """小数比例 → 百分比：`0.25` → `25.00%`。"""
    return UNKNOWN if is_missing(value) else f"{value * 100:.2f}%"


#: 币种代码 → 显示名。只管「怎么称呼」：汇率换算是 v2.0.0 的事，
#: 这张表回答不了、也不该假装能回答「一美元值多少人民币」。
CURRENCY_LABELS = {"CNY": "人民币", "USD": "美元", "HKD": "港币"}


def currency_label(code: str) -> str:
    """币种的显示名。表里没有的原样返回代码——编一个名字比显示 `SGD` 更糟。"""
    return CURRENCY_LABELS.get(code, code)


def format_quantity(value) -> str:
    """数量，去掉多余的零：`1000.0` → `1000`，`0.5` → `0.5`。"""
    if is_missing(value):
        return UNKNOWN
    if value == int(value):
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")
