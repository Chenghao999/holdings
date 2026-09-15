"""市场、资产类型、交易类型的枚举定义。"""

from enum import Enum


class MarketType(str, Enum):
    """市场类型。"""

    A_SHARE = "A股"
    US_STOCK = "美股"
    GOLD = "黄金"


class AssetType(str, Enum):
    """资产类型。"""

    STOCK = "stock"
    ETF = "etf"
    GOLD = "gold"


class TradeType(str, Enum):
    """交易类型。

    - BUY：买入，费用摊入持仓成本；
    - SELL：卖出，数量减少、成本价不变；
    - FEE：独立费用记录（手续费、托管费、管理费等），不改变数量与成本。
    """

    BUY = "BUY"
    SELL = "SELL"
    FEE = "FEE"
