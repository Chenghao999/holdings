"""交易写入服务：落库前做领域校验，避免把账算坏。

`calculator` 是纯函数，只在重放时按需校验；真正的写入闸门在这里——
所有**改动账本**的路径（`add`、`import`、`remove`）都必须经过本模块，
而不是直接调 DAO。删除看起来不涉及校验，但它是「`cli` 不直接碰 storage」
这条铁律的一部分：绕过它，账本就有了第二条不受管的写入路径。
"""

from __future__ import annotations

from dataclasses import dataclass

from holdings.models.transaction import Transaction, dedupe_key
from holdings.portfolio import calculator
from holdings.storage import transaction_dao


@dataclass(frozen=True)
class Duplicate:
    """这批里被判为「已经存在」的一笔。`index` 是它在传入列表里的位置。"""

    index: int
    #: 库里那笔的 id；同一批内部重复时为 None
    existing_id: int | None = None
    #: 同一批里更早出现的那一笔的位置；与库里重复时为 None
    earlier: int | None = None


def _in_order(history: list[Transaction], incoming: list[Transaction]) -> list[Transaction]:
    """把待写入交易按 (trade_date, id) 插进历史序列的正确位置。

    新交易尚无 id，同日交易里排在最后——与 transaction_dao.get_all 的
    `ORDER BY trade_date, id` 保持一致，否则补录往日交易时会用错误的持仓状态校验。
    """
    keyed = [(t.trade_date, t.id if t.id is not None else 0, t) for t in history]
    keyed += [(t.trade_date, float("inf"), t) for t in incoming]
    keyed.sort(key=lambda item: (item[0], item[1]))
    return [tx for _, _, tx in keyed]


def find_duplicates(db_path: str, txs: list[Transaction]) -> list[Duplicate]:
    """找出这批交易里**已经存在**的那些，按传入顺序返回。

    两处都算存在：

    - **库里已有**：逐月补充导出的对账单必然撞上——本月导出的文件里含上月
      最后几笔。这是本项要修的那个「导两遍账翻倍」；
    - **同一批里前面出现过**：有些券商自己的导出就带重复行。只查库的话，
      这种文件仍会静默翻倍，而它和前者是同一件事。

    只**报告**，不动数据：是丢掉还是照写，由调用方决定（`import --dedupe`）。
    """
    existing = {dedupe_key(tx): tx.id for tx in transaction_dao.get_all(db_path)}
    seen: dict[tuple, int] = {}
    duplicates: list[Duplicate] = []
    for index, tx in enumerate(txs):
        key = dedupe_key(tx)
        if key in existing:
            duplicates.append(Duplicate(index=index, existing_id=existing[key]))
        elif key in seen:
            duplicates.append(Duplicate(index=index, earlier=seen[key]))
        else:
            seen[key] = index
    return duplicates


def add_transaction(db_path: str, tx: Transaction) -> int:
    """校验后写入一笔交易，返回自增 id。"""
    return add_transactions(db_path, [tx])[0]


def add_transactions(db_path: str, txs: list[Transaction]) -> list[int]:
    """校验后**整批**写入交易，返回自增 id 列表。

    先把待写入交易与历史交易合并、按时间顺序严格重放一遍，确认其中任何一笔
    都不会让持仓越界（买入数量非正、卖出超过当时持有量），再交给 DAO 一次提交。
    校验失败时一笔都不写，避免 CSV 导入中途报错却留下半批数据。
    """
    pending = list(txs)
    if not pending:
        return []
    history = transaction_dao.get_all(db_path)
    calculator.compute_positions(_in_order(history, pending), strict=True)
    return transaction_dao.add_many(db_path, pending)


def get_transaction(db_path: str, tx_id: int) -> Transaction | None:
    """按 id 取一笔，不存在返回 None。"""
    return transaction_dao.get(db_path, tx_id)


def remove_transaction(db_path: str, tx_id: int) -> bool:
    """删除一笔交易，返回是否真的删掉了一条。"""
    return transaction_dao.remove(db_path, tx_id)
