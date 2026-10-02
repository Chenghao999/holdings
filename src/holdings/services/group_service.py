"""组合（`portfolio_group`）的管理：列出有哪些组合、改名、合并。

与 `portfolio_service` 的分工：那边把交易流水算成持仓汇总，这边只管
「有哪些组合」和「把历史数据从一个组合搬到另一个」，不自己算任何数。

**每个组合的汇总一律复用 `get_summary(db_path, group=g)`**，所以
`holdings group list` 里每一行的数，与 `holdings list --group <名字>` 底下那行汇总
由构造保证一致——两处各写一份算法的话，改了口径只会让其中一处悄悄走样。
代价是 G 次汇总、每次重读一遍这个组合的交易（N+1）：G 是手工维护的账户数
（几个），不是数据规模，换来的是「同一口径只有一处实现」。
"""

from __future__ import annotations

from dataclasses import dataclass

from holdings.exceptions import RecordNotFoundError, TradeValidationError
from holdings.services import portfolio_service
from holdings.storage import transaction_dao


@dataclass
class GroupRow:
    """一个组合，连同它在既有口径下的汇总。

    持有 `PortfolioSummary` 本体而不是抄一份标量出来：`total_value` 等在
    「一个标的都计不进来」时是 `None`（渲染成 `—`），抄字段就是把那条口径
    又复制一遍，日后服务层改了判断这里会跟不上。
    """

    group: str
    summary: portfolio_service.PortfolioSummary

    @property
    def incomplete(self) -> bool:
        """这个组合里有标的没进汇总（没行情，或非基准货币计价）。"""
        return bool(self.summary.unpriced_symbols or self.summary.foreign_holdings)


def list_groups(db_path: str) -> list[GroupRow]:
    """列出出现过的组合及其汇总，按名称升序（`transaction_dao.list_groups` 已排序）。"""
    return [
        GroupRow(group=name, summary=portfolio_service.get_summary(db_path, group=name))
        for name in transaction_dao.list_groups(db_path)
    ]


def default_group_note(name: str) -> str:
    """改动了 config.yaml `default_group` 指定的那个组合时要补的提醒。

    `holdings add` 不带 `--group` 时落到 `default_group` 那个名字上。改了名
    （或并走）之后，那条路会落在一个**新出现的**组合上——交易没丢，但会
    悄悄分成两处。所以改名本身照做，只是要说出来。

    这句话放在服务层，与 `portfolio_service.unpriced_hint` 同理：它是口径的一部分，
    界面只负责上色。
    """
    return (
        f"注意：config.yaml 的 default_group 仍是『{name}』，"
        f"holdings add 不带 --group 时还会写到这个名字上"
    )


def rename_group(db_path: str, old: str, new: str) -> int:
    """把组合 `old` 改名为 `new`，返回受影响的交易条数。"""
    old = old.strip()
    new = new.strip()
    if not new:
        raise TradeValidationError("组合名不能为空")

    existing = transaction_dao.list_groups(db_path)
    if old not in existing:
        raise RecordNotFoundError(f"组合『{old}』不存在")
    if old == new:
        # 幂等而非报错：要的结果已经在了，脚本重复执行不该变成失败。
        # 必须早于下面「名字被占用」的判断——否则是自己撞自己。
        return 0
    if new in existing:
        # 静默合并会让「改名」这条命令的语义变得比名字大；要说清它做不到，
        # 并给出真能达成目的的那条命令。
        raise TradeValidationError(
            f"组合『{new}』已存在。若要把『{old}』并入『{new}』，"
            f"请执行：holdings group merge {old} {new}"
        )
    return transaction_dao.move_group(db_path, old, new)


def merge_groups(db_path: str, source: str, target: str) -> int:
    """把组合 `source` 的交易全部并入 `target`，返回条数。`source` 之后不再存在。"""
    source = source.strip()
    target = target.strip()
    if not source or not target:
        raise TradeValidationError("组合名不能为空")
    if source == target:
        raise TradeValidationError("源组合与目标组合是同一个，无需合并")

    existing = transaction_dao.list_groups(db_path)
    if source not in existing:
        raise RecordNotFoundError(f"组合『{source}』不存在")
    if target not in existing:
        # 写错目标名时最容易发生的误解是「那就改名过去好了」——给出去路。
        raise RecordNotFoundError(
            f"目标组合『{target}』不存在。若只是想改名，"
            f"请用：holdings group rename {source} {target}"
        )
    return transaction_dao.move_group(db_path, source, target)
