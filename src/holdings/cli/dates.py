"""命令行日期参数的解析与校验。

`--date` / `--start` 都要「YYYY-MM-DD，非法值给退出码 5」，此前只有 `add` 里
一份回调，`chart --start` 干脆没校验。收在这里，两处共用同一份提示文案。
"""

from __future__ import annotations

from datetime import date

import click


def parse_iso_date(value: str) -> date:
    """把 YYYY-MM-DD 解析成 date；非法值交给 click 报错（退出码 5）。"""
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise click.BadParameter(f"不是合法日期（应为 YYYY-MM-DD）：{value}") from None


def with_today_default(_ctx: click.Context, _param: click.Parameter, value: str | None) -> date:
    """`--date` 的回调：不传就是今天。"""
    return date.today() if value is None else parse_iso_date(value)


def optional(_ctx: click.Context, _param: click.Parameter, value: str | None) -> date | None:
    """`--start` 的回调：不传就是不限起始日期。

    与 `with_today_default` 分开，因为「不传」在两种参数上含义不同——
    交易日期不传=今天，起始日期不传=从最早一条开始。
    """
    return None if value is None else parse_iso_date(value)
