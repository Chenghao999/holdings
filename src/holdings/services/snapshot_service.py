"""资产快照服务：记录与读取快照。

CLI 经由本模块访问 `snapshot_dao`，不直接碰 `storage`（架构铁律 3）。
`cli/commands/snapshot.py` 此前直接 `from holdings.storage import snapshot_dao`，
是 [BACKLOG B-11](../docs/BACKLOG.md) 记下的三处违反之一——这次因为要新增
快照列表命令而一并收口：再让新命令直接调 DAO，等于把违反从一处变成两处。
"""

from __future__ import annotations

from holdings.models.snapshot import Snapshot
from holdings.storage import snapshot_dao


def record(db_path: str, snap: Snapshot) -> int:
    """记录一份快照，返回其 id。同一日期重复记录会抛 DatabaseError。"""
    return snapshot_dao.add(db_path, snap)


def list_all(db_path: str) -> list[Snapshot]:
    """按日期升序返回全部快照。"""
    return snapshot_dao.get_all(db_path)
