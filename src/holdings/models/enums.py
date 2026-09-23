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


class NonTradeType(str, Enum):
    """对账单里认得出、但本工具**不入账**的行。

    它们都是真实发生过的事件，不入账各有各的原因：分红、送转、配股会改变数量
    或成本价，口径尚未支持（见 `docs/BACKLOG.md` 的 B-23）；银证转账与利息
    动的是现金，与持仓无关。

    > 不入账**不等于可以不提**。静默跳过会让「导入成功」变成假话——用户看到的
    > 是一份导完的对账单，实际少了会改成本的那几行，而退出码是 0、数字看着也对。
    > 所以 `import` 会把它们逐行列出行号与原因，见 `docs/USER_GUIDE.md` 的分类表。
    """

    DIVIDEND = "分红派息"
    BONUS_SHARE = "送股转增"
    RIGHTS_ISSUE = "配股"
    TRANSFER = "银证转账"
    INTEREST = "利息"


#: 各家券商对同一件事的叫法不同（「红利入账」「派息」说的都是分红派息）。
#: 这里是**通用词表**，不是某一家券商的映射——券商自己那一列的叫法由
#: `data/brokers/` 的解析器负责翻译（见 `docs/BACKLOG.md` 的 B-28）。
#: 每类给几种常见写法即可，认不出仍然是整批拒绝，不会当成不入账放过。
NON_TRADE_ALIASES: dict[str, NonTradeType] = {
    "分红": NonTradeType.DIVIDEND,
    "分红派息": NonTradeType.DIVIDEND,
    "股息": NonTradeType.DIVIDEND,
    "红利": NonTradeType.DIVIDEND,
    "红利入账": NonTradeType.DIVIDEND,
    "派息": NonTradeType.DIVIDEND,
    "送股": NonTradeType.BONUS_SHARE,
    "送转股": NonTradeType.BONUS_SHARE,
    "送股转增": NonTradeType.BONUS_SHARE,
    "转增": NonTradeType.BONUS_SHARE,
    "转增股本": NonTradeType.BONUS_SHARE,
    "配股": NonTradeType.RIGHTS_ISSUE,
    "配股缴款": NonTradeType.RIGHTS_ISSUE,
    "银证转账": NonTradeType.TRANSFER,
    "银行转证券": NonTradeType.TRANSFER,
    "证券转银行": NonTradeType.TRANSFER,
    "利息": NonTradeType.INTEREST,
    "利息归本": NonTradeType.INTEREST,
    "结息": NonTradeType.INTEREST,
}


def classify_trade_type(raw: str) -> TradeType | NonTradeType | None:
    """把对账单里一行的「业务名称」归到已知类别。

    三种结果对应三种处置，调用方**必须**区别对待：

    - `TradeType`：入账；
    - `NonTradeType`：认得出、不入账，必须逐行报出来；
    - `None`：认不出——那是「这个值非法」，应当整批拒绝，而不是当成不入账
      静默放过。两者的处置相反：前者要用户改文件，后者只要用户知道。
    """
    text = raw.strip()
    try:
        return TradeType(text)
    except ValueError:
        return NON_TRADE_ALIASES.get(text)
