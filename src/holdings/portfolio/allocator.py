"""资产配置占比计算（纯函数）。"""

from __future__ import annotations


def allocation_by_asset_type(
    holdings_market_value: dict[str, float],
    asset_types: dict[str, str],
) -> dict[str, float]:
    """按资产类型汇总占比。

    holdings_market_value: symbol -> 市值
    asset_types: symbol -> asset_type
    返回 asset_type -> 占比（0~1）。
    """
    totals: dict[str, float] = {}
    for symbol, value in holdings_market_value.items():
        atype = asset_types.get(symbol, "stock")
        totals[atype] = totals.get(atype, 0.0) + value
    total = sum(totals.values())
    if total <= 0:
        return dict.fromkeys(totals, 0.0)
    return {k: v / total for k, v in totals.items()}
