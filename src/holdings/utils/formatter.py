"""金额 / 百分比格式化，纯函数。"""


def format_money(value: float, currency: str = "CNY") -> str:
    """格式化为千分位金额字符串。"""
    return f"{value:,.2f} {currency}"


def format_percent(value: float) -> str:
    """格式化为百分比字符串。"""
    return f"{value:.2f}%"


def format_quantity(value: float) -> str:
    """格式化数量，去掉多余的零。"""
    if value == int(value):
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")
