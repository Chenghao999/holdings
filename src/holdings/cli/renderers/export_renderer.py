"""把一份 `Dataset` 写成 CSV / JSON 文件。

与 `chart_renderer` 同一个位置、同一个分工：服务层算出内容，这里负责落盘。
两种格式的差别只在这一个文件里，命令层不必知道 `None` 该写成什么。
"""

from __future__ import annotations

import csv
import json
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from holdings.services.export_service import Dataset


def write_csv(columns: tuple[str, ...], rows: list[dict], path: str) -> None:
    """写 CSV：第一行表头，之后一行一条记录。

    编码用 **`utf-8-sig`**（带 BOM）：不带 BOM 的 UTF-8 CSV 在 Excel 里双击
    打开是乱码，而导出的持仓表十有八九就是要拿去 Excel 里看的。这不是单向
    取舍——本工具自己的 `data/brokers/encoding.py` 第一个剥的就是 BOM，所以
    带 BOM 的导出**照样导得回来**。两处是一对，改任一处都得回头看另一处。

    `None` 写成空单元格，这是 `csv` 模块对 `None` 的既定行为（写成 `None`
    四个字母才是灾难）。用例把这条钉住了，换个写法会红。

    行尾用 `\\n`（`csv` 模块默认是 `\\r\\n`）：本仓库全仓 LF，导出的文件跟着
    走。两种行尾 Excel 都认。
    """
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(columns: tuple[str, ...], rows: list[dict], path: str) -> None:
    """写 JSON：一个对象数组，键就是表头。

    `columns` 收下但不用：JSON 的每个对象自带键名，0 行时就是 `[]`。签名与
    `write_csv` 对齐，两者才好在 `WRITERS` 那张表里互换。

    编码用 `utf-8` 而**不是** `utf-8-sig`：BOM 是给 Excel 认 CSV 用的，
    JSON 前面多一个 BOM 只会让一部分解析器当场报错。

    `allow_nan=False` 是故意的：默认 `json.dumps` 会把 `NaN` / `Infinity`
    原样写出去，而它们**不是合法 JSON**——`jq` 与浏览器的 `JSON.parse` 读到
    就报错。缺失值本来就该在那之前变成 `null`（见 `export_service._plain`），
    这条是防线：宁可写不出来，也不写一份别人读不了的文件。
    """
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


#: 格式名 → 写入函数。`--format` 的选项由这张表派生，不在命令里另写一份。
WRITERS: dict[str, Callable[[tuple[str, ...], list[dict], str], None]] = {
    "csv": write_csv,
    "json": write_json,
}


def write(dataset: Dataset, path: str, fmt: str) -> None:
    """把一份 `Dataset` 写成文件。

    格式名对不上是 `KeyError`：`--format` 的选项由 `WRITERS` 派生，走不到
    这里；真走到了说明有人加了格式却没加写入函数。
    """
    WRITERS[fmt](dataset.columns, dataset.rows, path)
