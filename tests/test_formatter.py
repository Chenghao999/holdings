"""`utils/formatter.py`：一处定义「一个数该怎么显示」。

这些函数此前零调用（B-12 的死代码），渲染层各写各的格式化与空值判断。
接上之后它们有了真实调用点，也就值得测。
"""

from __future__ import annotations

import pytest

from holdings.utils.formatter import (
    UNKNOWN,
    currency_label,
    format_money,
    format_number,
    format_percent,
    format_price,
    format_quantity,
    format_ratio,
    is_missing,
)


@pytest.mark.parametrize(
    ("func", "value", "expected"),
    [
        (format_money, 1234.5, "1,234.50"),
        (format_money, 0.0, "0.00"),
        (format_price, 4.8521, "4.8521"),
        (format_number, 1.5, "1.50"),
        (format_percent, 4.13, "4.13%"),
        (format_ratio, 0.25, "25.00%"),
        (format_quantity, 1000.0, "1000"),
        (format_quantity, 0.5, "0.5"),
        (format_quantity, 10.25, "10.25"),
    ],
)
def test_formats(func, value, expected):
    assert func(value) == expected


def test_ratio_and_percent_are_not_interchangeable():
    """两种口径分开成两个函数，正是为了防止把 0.25 印成「0.25%」。"""
    assert format_ratio(0.25) == "25.00%"
    assert format_percent(0.25) == "0.25%"


@pytest.mark.parametrize("value", [None, float("nan")])
def test_missing_values_render_as_a_dash(value):
    """`None` 与 pandas 存的 `NaN` 都要认，且都显示 `—` 而不是 0。"""
    assert is_missing(value)
    for func in (
        format_money,
        format_price,
        format_number,
        format_percent,
        format_ratio,
        format_quantity,
    ):
        assert func(value) == UNKNOWN


@pytest.mark.parametrize(
    ("code", "expected"),
    [("CNY", "人民币"), ("USD", "美元"), ("HKD", "港币")],
)
def test_currency_labels(code, expected):
    assert currency_label(code) == expected


def test_an_unknown_currency_falls_back_to_its_code():
    """表里没有的币种原样显示代码——编一个名字比显示 `SGD` 更糟。"""
    assert currency_label("SGD") == "SGD"


def test_zero_is_not_missing():
    """0 是一个结论，`—` 是「算不出来」。两者不能混。"""
    assert not is_missing(0.0)
    assert format_money(0.0) == "0.00"
    assert format_percent(0.0) == "0.00%"
