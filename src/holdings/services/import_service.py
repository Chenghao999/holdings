"""对账单导入的取数编排：文件 → 规范行。

读文件、探编码、挑解析器这些事都在 `data/brokers/` 里；`cli` 不许直接 import
`data`（ARCHITECTURE 铁律 3），由这一层端给表现层。规矩与 `sync_service`
把 `data` + `storage` 串起来是同一套。
"""

from __future__ import annotations

from holdings.data import brokers
from holdings.models.statement import Statement


def read_statement(
    path: str, *, broker: str | None = None, fee_column: str | None = None
) -> Statement:
    """读一份对账单。

    `broker` 为空则按表头自动识别；识别不出、或认出多个，都报错而不是猜一个。
    """
    return brokers.parse_file(path, broker=broker, fee_column=fee_column)
