"""券商对账单解析：一家券商一个模块，这里把它们收进注册表。

`data/` 本来就是「外部世界 → 领域对象」的适配层，对账单文件与行情 API 同属
「外部数据的来源」，所以放这儿而不是新开一层（见 `docs/ARCHITECTURE.md`）。

**加一家券商 = 加一个模块 + 在 `BROKERS` 里加一行**，`import_cmd.py` 与
`fetcher.py` 都不用改。
"""

from __future__ import annotations

import pathlib

from holdings.data.brokers.base import (
    REQUIRED_COLUMNS,
    SAMPLE_ROWS,
    BrokerParser,
    read_table,
)
from holdings.data.brokers.canonical import CanonicalCsv
from holdings.data.brokers.demo_a import DemoA
from holdings.data.brokers.demo_b import DemoB
from holdings.data.brokers.encoding import decode_statement
from holdings.exceptions import TradeValidationError
from holdings.models.statement import Statement, StatementRow

__all__ = [
    "BROKERS",
    "REQUIRED_COLUMNS",
    "BrokerParser",
    "Statement",
    "StatementRow",
    "broker_names",
    "decode_statement",
    "detect",
    "get_broker",
    "parse_file",
]

#: 全部已注册的格式。**顺序与识别无关**：识别要求唯一命中，命中多个时报错
#: 而不是取第一个（见 `detect`）。
BROKERS: tuple[BrokerParser, ...] = (CanonicalCsv(), DemoA(), DemoB())


def broker_names() -> tuple[str, ...]:
    """已注册的格式名，按注册顺序。报错文案从这里取，免得两处各写一份。"""
    return tuple(broker.name for broker in BROKERS)


def get_broker(name: str) -> BrokerParser:
    """按 `--broker` 给的名字取解析器。对不上就列出可用的，不猜一个最像的。"""
    wanted = name.strip().lower()
    broker = next((b for b in BROKERS if b.name == wanted), None)
    if broker is None:
        raise TradeValidationError(
            f"没有名为 {name} 的对账单格式，可用：{'、'.join(broker_names())}"
        )
    return broker


def detect(header: list[str], sample: list[list[str]]) -> BrokerParser:
    """按表头判断这是哪一家的格式。

    **命中不唯一就报错，不猜。**猜错的代价是整批数字错，而用户会以为导成功了；
    让他多打一个 `--broker`，比让他对着一份错的持仓找一星期强。
    """
    matched = [broker for broker in BROKERS if broker.matches(header, sample)]
    if len(matched) == 1:
        return matched[0]
    if not matched:
        raise TradeValidationError(
            f"认不出这份对账单的格式，请用 --broker 指定（可用：{'、'.join(broker_names())}）"
        )
    raise TradeValidationError(
        f"这份表头同时符合 {'、'.join(b.label for b in matched)}，请用 --broker 指定"
    )


def parse_file(path: str, *, broker: str | None = None, fee_column: str | None = None) -> Statement:
    """读一份对账单：探编码 → 定格式 → 翻译成规范行。"""
    raw = pathlib.Path(path).read_bytes()
    text = decode_statement(raw)

    table = read_table(text)
    if not table:
        # 空文件走识别只会得到「认不出这份对账单的格式」，对着一份空文件
        # 说这话等于没说——它确实是空的，不是在冒充别家的格式。
        raise TradeValidationError("这份对账单是空的：没有表头，也没有数据行")

    header = [cell.strip() for cell in table[0]]
    parser = get_broker(broker) if broker else detect(header, table[1 : SAMPLE_ROWS + 1])
    return Statement(broker_label=parser.label, rows=parser.parse(text, fee_column=fee_column))
