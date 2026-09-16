"""数据模型层：Pydantic DTO 与枚举定义，零内部依赖。

这里**不再重新导出**各模块的类。此前 `__init__.py` 里 import 了
`AssetType` / `MarketType` / `Snapshot` / `TradeType` / `Transaction` 并列入
`__all__`，但全项目没有一处 `from holdings.models import X`——那是零调用的
转发代码（[B-12](../docs/BACKLOG.md)），而且它没有跟着新增的 `AssetMeta` 一起
维护，本身就是「这份清单没人看」的证据。

各模块直接 import 即可：`from holdings.models.transaction import Transaction`。
"""
