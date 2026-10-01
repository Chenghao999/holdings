"""导出的取数编排：账本 / 持仓表 / 快照 → 「表头 + 行」的纯数据。

导出什么、每列叫什么，都在这一层定；写成 CSV 还是 JSON、写进哪个文件，是
表现层的事（`cli/renderers/export_renderer.py`）。分法与 `chart_service` 给
`Figure`、`chart_renderer` 落盘是同一套：服务层不碰文件，界面层不取数。

**只有账本那一份是能导回去的。** 它的表头从 `data/brokers/canonical.py`
派生，也就是 `holdings import` 认的那一份；持仓表与快照是给人看/报税用的，
没有对应的导入路径。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from holdings.data.brokers.canonical import CanonicalCsv
from holdings.models.snapshot import Snapshot
from holdings.models.transaction import Transaction
from holdings.services import portfolio_service
from holdings.storage import snapshot_dao, transaction_dao


@dataclass(frozen=True)
class Dataset:
    """一份待写出的数据：列的顺序、每行的值、空的时候说一句什么。

    `rows` 里的值必须已经是**能直接写进文件的标量**：数字是 Python 的
    int / float，文本是 str，算不出来的值是 `None`（不是 NaN，也不是 numpy
    标量）——「缺失写成什么样」是两个格式各自的事（CSV 写空单元格、JSON 写
    `null`），不该让渲染层再去判断一个 pandas 对象。`tests/test_export.py`
    有一条用例拿 `json.dumps` 把三份数据逐份过一遍，钉的就是这个契约。

    `empty_hint` 只在 0 行时用得上：导出空库不是错误（一个刚 `init` 完的库
    本来就该导得出东西），但「0 行」得说清是**库里本来就没有**，而不是筛掉了
    或者写失败了。
    """

    columns: tuple[str, ...]
    rows: list[dict]
    empty_hint: str


# ------------------------------------------------------------------ 账本


def ledger_columns() -> tuple[str, ...]:
    """账本的表头：每个字段在 `canonical.py` 里的第一种写法。

    做成函数而不是模块级常量，是为了让它每次**现读** `CanonicalCsv.columns`：
    常量在 import 时就算死了，`tests/test_export.py` 里那条「往 canonical 加
    一列，导出的表头跟着变」的用例便无从验证。
    """
    return tuple(CanonicalCsv.columns[field][0] for field in CanonicalCsv.columns)


def _ledger_values(tx: Transaction) -> dict[str, object]:
    """一笔交易 → 每个字段的值，键是 canonical 的字段名。

    与 `import_cmd._row_to_transaction` 是互逆的两半：那边把单元格读成
    `Transaction`，这边把 `Transaction` 写回单元格。两处都得跟着
    `CanonicalCsv.columns` 走，改动一处就得回头看另一处。
    """
    return {
        "symbol": tx.symbol,
        "market": tx.market.value,
        "asset_type": tx.asset_type.value,
        "trade_date": tx.trade_date.isoformat(),
        "trade_type": tx.trade_type.value,
        "quantity": tx.quantity,
        "price": tx.price,
        "fee": tx.fee,
        # 没有备注时是 None，会写成空单元格；空串与 NULL 的区分留在库里，
        # 导出文件里两者本来就分不出来，不必假装分得出。
        "notes": tx.notes,
        "external_id": tx.external_id,
        # 组合分组走 `account` 这一列：canonical 把它定义成「资金账号」，
        # 与 `transactions.portfolio_group` 是同一件事（B-32 定的口径）。
        "account": tx.portfolio_group,
    }


def _ledger_row(tx: Transaction) -> dict:
    """一行交易 → 一组单元格，**列的顺序与拼写都取自 canonical**。

    这里用的是字典推导而不是逐列写死：往 `CanonicalCsv.columns` 加一个字段
    而忘了在上面的 `_ledger_values` 里填值，会当场 `KeyError`，而不是让导出的
    文件从此少一列——少的那一列要等到「导回来发现数据缺了」才会被发现。
    """
    values = _ledger_values(tx)
    return {CanonicalCsv.columns[field][0]: values[field] for field in CanonicalCsv.columns}


def ledger(db_path: str) -> Dataset:
    """交易流水，按本工具自己的标准 CSV 表头。

    这份是**能导回去的**：`holdings import` 认得它。数量与金额原样写出
    （Python 的浮点 repr 自带「读回来还是同一个数」的保证），不做四舍五入，
    也不做「好看」的格式化——备份的职责是原样保存，不是排版。

    唯一的减项是 `source`（这笔是从哪份对账单读进来的）：canonical 格式里
    没有这一列，导回来一律记成 `csv`。这是句实话——这一行确实是从标准 CSV
    读进来的；为它单开一列就得改 `import` 的契约，换来的是一条只对备份
    有意义的元数据。
    """
    rows = [_ledger_row(tx) for tx in transaction_dao.get_all(db_path)]
    return Dataset(ledger_columns(), rows, "库里还没有交易记录")


# ------------------------------------------------------------------ 持仓表

#: 持仓表导出的列。
#:
#: 前 11 列就是终端 `holdings list` 显示的那 11 列——顺序也照它，
#: `HOLDINGS_COLUMNS` 那份契约在服务层，这里派生而不是另抄一份。
#:
#: 末尾补的 `currency` 不进终端表格（人民币是默认口径，每行都挂一个 `CNY`
#: 只是占地方），但**导出到文件里必须留着**：少了它，一份含美股的持仓表就
#: 分不清哪一行的市值是美元——正是 B-19 花力气排除的那种「看着像结论」的错数。
HOLDINGS_EXPORT_COLUMNS: tuple[str, ...] = (*portfolio_service.HOLDINGS_COLUMNS, "currency")


def _plain(value):
    """DataFrame 里的一个格子 → 能直接写进文件的标量。

    缺失值一律变 `None`：CSV 里写 `nan` 在 Excel 里看着像个词，JSON 里的
    `NaN` 更**不是合法 JSON**——`json.dumps` 默认会把它原样写出去，`jq` 与
    浏览器的 `JSON.parse` 读到就报错。

    这一步不是「防万一」：一部分标的取到行情、另一部分没取到时，pandas 会把
    那一列变成 float64 并把缺的填成真正的 `NaN`（整列都缺时反而是 object 列
    的 `None`），`holdings` 表里这两种情况都常见。

    数值本身不动——`to_dict("records")` 给出来的已经是 Python 标量，
    没有 numpy 类型要还原。
    """
    return None if pd.isna(value) else value


def holdings(db_path: str) -> Dataset:
    """当前持仓表：`holdings list` 那张表，外加币种一列。

    列名用英文（就是 `holdings_df` 的列名），不换成 `HOLDINGS_COLUMNS` 里那套
    中文显示名：那份中文是**渲染层**的叫法（`--sort` 也接受它们），而导出的
    文件是一份数据，该跟服务层的产出对齐。

    没有行情的标的在这里不是缺行，是几个空单元格：市值、盈亏算不出来，
    但「持有什么、持有多少、成本多少」是账本事实，照写。
    """
    df = portfolio_service.get_summary(db_path).holdings_df
    rows = [
        {column: _plain(record.get(column)) for column in HOLDINGS_EXPORT_COLUMNS}
        for record in df.to_dict("records")
    ]
    return Dataset(HOLDINGS_EXPORT_COLUMNS, rows, "库里还没有持仓")


# ------------------------------------------------------------------ 快照

#: 快照导出的列：`snapshots` 表那几列，去掉自增 `id`。
#:
#: `id` 是本地的代理键，换一个库就会变，写进备份只会误导。`created_at` 留着：
#: 「什么时候记下的」是这份手记的一部分——快照恰恰是补不回来的那种数据，
#: 交易流水还能从券商重导，手记的日子不能。
SNAPSHOT_COLUMNS: tuple[str, ...] = (
    "snapshot_date",
    "total_value",
    "equity_value",
    "gold_value",
    "cash_balance",
    "note",
    "created_at",
)


def _snapshot_row(snapshot: Snapshot) -> dict:
    return {
        "snapshot_date": snapshot.snapshot_date.isoformat(),
        "total_value": snapshot.total_value,
        "equity_value": snapshot.equity_value,
        "gold_value": snapshot.gold_value,
        "cash_balance": snapshot.cash_balance,
        "note": snapshot.note,
        "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
    }


def snapshots(db_path: str) -> Dataset:
    """资产快照，按日期升序——与 `holdings snapshots` 看到的顺序一致。"""
    rows = [_snapshot_row(snapshot) for snapshot in snapshot_dao.get_all(db_path)]
    return Dataset(SNAPSHOT_COLUMNS, rows, "库里还没有快照")


# ------------------------------------------------------------------ 分发

#: `--what` 的取值 → 取数函数。加一份导出 = 加一个函数 + 这一行。
BUILDERS: dict[str, Callable[[str], Dataset]] = {
    "ledger": ledger,
    "holdings": holdings,
    "snapshots": snapshots,
}


def build(what: str, db_path: str) -> Dataset:
    """按名字取一份数据集。

    名字对不上是 `KeyError`：`--what` 的选项由 `BUILDERS` 本身派生，走不到
    这里；真走到了说明有人加了选项却没加取数函数。
    """
    return BUILDERS[what](db_path)
