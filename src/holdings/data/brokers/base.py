"""对账单解析器的公共骨架：一家券商 = 一个子类 + 四张映射表。

`matches` 与 `parse` 都在这里实现，子类**不写逻辑、只填表**。这是刻意的：
解析器一旦能自由发挥，各家就会各写一套「什么算一行」「空行怎么办」，
换一家券商就要重读一遍别人的分支。映射表装不下时再覆写方法，那时也看得见
是在哪一处破了例。
"""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation
from typing import ClassVar

from holdings.exceptions import TradeValidationError
from holdings.models.statement import StatementRow

#: 一份对账单至少要能变出这几列，缺一列就没法记账。
REQUIRED_COLUMNS: tuple[str, ...] = ("symbol", "trade_date", "trade_type", "quantity", "price")

#: 识别时最多看几行数据。基类不看值，只有「两种导出表头一样、只能看值区分」
#: 的券商才用得上；给个上限免得为了识别把整个文件读进内存。
SAMPLE_ROWS = 5


def read_table(text: str) -> list[list[str]]:
    """按 CSV 切成单元格矩阵。第一行是表头。

    用 `csv.reader` 按**位置**读，而不是 `DictReader` 按列名读：券商导出的
    表头常带尾随空格或重复列名，按名字取值会取错列还不报错。
    """
    return list(csv.reader(io.StringIO(text, newline="")))


class BrokerParser:
    """一家券商的对账单格式。"""

    #: `--broker` 的取值，报错与文档里也用它
    name: ClassVar[str] = ""
    #: 报错时给人看的名字
    label: ClassVar[str] = ""

    #: 规范列名 → 本家的写法（按顺序取第一个在表头里出现的）
    columns: ClassVar[dict[str, tuple[str, ...]]] = {}
    #: 本家「业务名称」→ 本工具认识的 trade_type。**没映射到的原样留着**，
    #: 交给 `models.enums.classify_trade_type`——分红 / 送转这些非买卖行是所有
    #: 券商共有的，不该让每家重写一遍，也不该在这里被静默丢掉。
    trade_types: ClassVar[dict[str, str]] = {}
    #: 本家「市场」写法 → MarketType 的值。不映射这一列就按默认的 A 股走。
    markets: ClassVar[dict[str, str]] = {}
    #: 费用拆在几列里时列在这里，解析时相加
    fee_columns: ClassVar[tuple[str, ...]] = ()

    # ------------------------------------------------------------------ 识别

    def matches(self, header: Sequence[str], sample: Sequence[Sequence[str]]) -> bool:
        """这份表头是不是本家的格式。

        只看**必需列**齐不齐：本家新导出一列不该让识别失败。`sample` 是头几行
        数据，基类不看——留着是给需要看值的券商覆写用的（见 `SAMPLE_ROWS`）。
        """
        resolved = self._resolve(list(header))
        return all(column in resolved for column in REQUIRED_COLUMNS)

    def _resolve(self, header: list[str]) -> dict[str, int]:
        """规范列名 → 它在表头里的下标。"""
        resolved: dict[str, int] = {}
        for canonical, aliases in self.columns.items():
            index = next((header.index(a) for a in aliases if a in header), None)
            if index is not None:
                resolved[canonical] = index
        return resolved

    # ------------------------------------------------------------------ 解析

    def parse(self, text: str, fee_column: str | None = None) -> list[StatementRow]:
        """把整份对账单解析成规范行。

        `fee_column` 是用户用 `--fee-column` 指定的列名，**照文件里的写法给**
        （用户是照着文件写的），它优先于本家自己的费用列。
        """
        table = read_table(text)
        if not table:
            return []

        header = [cell.strip() for cell in table[0]]
        resolved = self._resolve(header)
        self._check_header(header, resolved, fee_column)
        fee_index = header.index(fee_column) if fee_column else None

        rows: list[StatementRow] = []
        for line_no, cells in enumerate(table[1:], start=2):  # 第 1 行是表头
            if not any(cell.strip() for cell in cells):
                continue  # 券商导出的尾部常挂几行空行，那不是数据
            rows.append(self._to_row(cells, line_no, header, resolved, fee_index, fee_column))
        return rows

    def _to_row(
        self,
        cells: list[str],
        line_no: int,
        header: list[str],
        resolved: dict[str, int],
        fee_index: int | None,
        fee_column: str | None,
    ) -> StatementRow:
        def cell(index: int) -> str:
            return cells[index] if index < len(cells) else ""

        values = {canonical: cell(index) for canonical, index in resolved.items()}

        # 业务名称与市场都被翻译成规范取值；翻译不了的原样留着，
        # 让下游去判断「认得出但不入账」还是「根本不认识」。
        raw_type = values.get("trade_type", "")
        values["trade_type"] = self.trade_types.get(raw_type.strip(), raw_type)
        if "market" in values:
            values["market"] = self.markets.get(values["market"].strip(), values["market"])

        if fee_index is not None:
            values["fee"] = cell(fee_index)
            fee_source = str(fee_column)
        elif self.fee_columns:
            values["fee"] = self._sum_fees(cells, header, line_no)
            fee_source = "/".join(self.fee_columns)
        else:
            fee_source = "fee"  # 费用就在 `columns` 映射好的 fee 列里

        return StatementRow(line_no=line_no, values=values, fee_source=fee_source)

    def _sum_fees(self, cells: list[str], header: list[str], line_no: int) -> str:
        """把拆开的费用列加起来。加不了就报出是哪一列。

        用 `Decimal` 而不是 `float`：钱是十进制记的，`5.00 + 1.60 + 0.02`
        用浮点加出来是 `6.619999999999999`，存进库里就是那个数——报表上
        看不出来，但成本价从此带上一粒永远擦不掉的沙。

        返回字符串而不是数字：数值校验统一在 `import_cmd._row_to_transaction`
        里做，那里才知道报错要怎么拼。这里只在**必须**相加时才碰数字。
        """

        def cell(name: str) -> str:
            index = header.index(name)
            return (cells[index] if index < len(cells) else "").strip()

        present = [name for name in self.fee_columns if name in header]
        total = Decimal(0)
        for name in present:
            text = cell(name)
            if not text:
                continue  # 当天没有这一项，留空是常事
            try:
                total += Decimal(text)
            except InvalidOperation:
                raise TradeValidationError(
                    f"第 {line_no} 行 {name} 列不是合法数字：{text}"
                ) from None
        return str(total) if present else ""

    # ------------------------------------------------------------------ 表头

    def _check_header(
        self, header: list[str], resolved: dict[str, int], fee_column: str | None
    ) -> None:
        """缺列与不存在的费用列都在这里一次性说清楚。

        用 `TradeValidationError`（退出码 5）而不是 `click.BadParameter`：
        这些是文件内容的问题、不是命令行参数的问题，报错文案也就不该带
        「Invalid value for ...」这类 click 前缀。
        """
        missing = [column for column in REQUIRED_COLUMNS if column not in resolved]
        if missing:
            wanted = "、".join(self._describe(column) for column in missing)
            raise TradeValidationError(
                f"{self.label}：缺少必需列 {wanted}（现有列：{'、'.join(header)}）"
            )
        if fee_column and fee_column not in header:
            # 此前是静默按 0 计费，用户会以为费用导进来了。
            raise TradeValidationError(
                f"--fee-column 指定的列不存在：{fee_column}（现有列：{'、'.join(header)}）"
            )

    def _describe(self, canonical: str) -> str:
        """报错里怎么称呼一列：本家叫法与本工具的叫法不同时，两个都说。"""
        others = [alias for alias in self.columns.get(canonical, ()) if alias != canonical]
        return f"{canonical}（本家叫 {'/'.join(others)}）" if others else canonical
