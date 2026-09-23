"""本工具自己的格式：英文表头，即 `USER_GUIDE` 第 5 节里写的那种。

它也进注册表，好让「表头是英文」与「表头是券商中文」走**同一条路**——多一条
分支就多一处会跟另一处对不上的地方（编码、空行、行号都要各写一遍）。

识别上它是**兜底**：表头里只要有一个本工具认识的列名就算它。用户自己照着
文档写的 CSV 缺了哪列，直接指名道姓地报出来，比笼统的「认不出这份文件的
格式」有用得多；而券商的中文表头一个英文列名都不含，不会被它抢走。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar

from holdings.data.brokers.base import BrokerParser


class CanonicalCsv(BrokerParser):
    name = "csv"
    label = "标准 CSV"

    columns: ClassVar[dict[str, tuple[str, ...]]] = {
        "symbol": ("symbol",),
        "market": ("market",),
        "asset_type": ("asset_type",),
        "trade_date": ("trade_date",),
        "trade_type": ("trade_type",),
        "quantity": ("quantity",),
        "price": ("price",),
        "fee": ("fee",),
        "notes": ("notes",),
    }

    def matches(self, header: Sequence[str], sample: Sequence[Sequence[str]]) -> bool:
        """认出一个列名就算数——理由见模块开头的「兜底」一段。"""
        return any(alias in header for aliases in self.columns.values() for alias in aliases)
