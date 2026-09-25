"""对账单的中间表示：某一家的解析器翻译完、还没变成 `Transaction` 的一行。

它卡在「外部文件格式」与「本工具的交易」之间，所以既不属于 `data/`（那边只
翻译，不该知道什么算合法交易），也不属于 `cli/`（那边要做表现层的事）——
放在基础层，两层都取得到。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StatementRow:
    """对账单里的一行，列名已翻译成规范名。"""

    #: 原始文件里的行号（1 起，表头是第 1 行）。报错要能指回原文件，
    #: 而这个行号在解析器跳过尾部空行之后就再也推算不出来了，只能带着走。
    line_no: int
    #: 规范列名 → 单元格原文。缺少的列不在这里，取它是空串。
    values: dict[str, str]
    #: 费用取自哪一列，仅用于报错：券商对费用列的叫法不同（`佣金` / `手续费`），
    #: 有的还拆成「佣金 / 印花税 / 过户费」三列相加——报「fee 列不是数字」，
    #: 用户在自己的文件里找不到这一列。
    fee_source: str = "fee"

    def get(self, column: str) -> str:
        """取一列的值，去掉两端空白。没有这一列、或单元格是空的，都返回空串。"""
        return (self.values.get(column) or "").strip()


@dataclass(frozen=True)
class Statement:
    """一份读进来的对账单。"""

    #: 用的哪个解析器，人话名字。自动识别之后要能告诉用户它认成了谁——
    #: 认错了才有得查。
    broker_label: str
    #: 同一个解析器的**标识**（`--broker` 的取值），随每笔交易存进 `source` 列。
    #: 与人话名字分开：标识是拿去比对与查询的，改名不该让历史数据的来源对不上。
    broker_name: str
    rows: list[StatementRow]
