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
    - FEE：独立费用记录（手续费、托管费、管理费等），不改变数量与成本；
    - DIVIDEND：现金分红，摊薄持仓成本，股数不变；
    - BONUS_SHARE：送股 / 转增 / 拆股，总成本不变、股数增加。

    两个公司行为**沿用同一条列约定**：`quantity × price` 就是这一行的金额，
    与买入的「成交数量 × 成交单价」同构，`price` 永远是单价。
    各自的填法见 `docs/SCHEMA.md` 的类型表与 `docs/USER_GUIDE.md` 第 5 节。
    """

    BUY = "BUY"
    SELL = "SELL"
    FEE = "FEE"
    #: 现金分红：`quantity` = 持股数、`price` = 每股派息，金额 = 两者相乘。
    #: 摊薄成本（而不是记进 `fee`）的理由见 `calculator._apply_dividend`。
    DIVIDEND = "DIVIDEND"
    #: 送股 / 转增 / 拆股共用一种类型：三者对成本的影响是同一条——总成本不变、
    #: 股数变、成本价被摊薄。拆股不必单开一个，否则要维护两条一模一样的口径。
    BONUS_SHARE = "BONUS_SHARE"


class NonTradeType(str, Enum):
    """对账单里认得出、但本工具**仍不入账**的行。

    只剩三类，都不改持仓与成本价：配股要另外缴款、还有配售比例，口径尚未支持
    （用户可把它拆成一笔 `BUY` 手工补录，见 `docs/USER_GUIDE.md`）；银证转账与
    利息动的是现金，与持仓无关。

    > 不入账**不等于可以不提**。静默跳过会让「导入成功」变成假话——用户看到的
    > 是一份导完的对账单，实际少了会改成本的那几行，而退出码是 0、数字看着也对。
    > 所以 `import` 会把它们逐行列出行号与原因，见 `docs/USER_GUIDE.md` 的分类表。
    """

    RIGHTS_ISSUE = "配股"
    TRANSFER = "银证转账"
    INTEREST = "利息"


#: 各家券商对同一件事的叫法不同（「红利入账」「派息」说的都是分红派息）。
#: 这里是**通用词表**，不是某一家券商的映射——券商自己那一列的叫法由
#: `data/brokers/` 的解析器负责翻译（见 `docs/BACKLOG.md` 的 B-28）。
#: 每类给几种常见写法即可，认不出仍然是整批拒绝，不会当成不入账放过。
#:
#: 值可以是两种枚举：指到 `TradeType` 的会入账，指到 `NonTradeType` 的仍然
#: 只逐行报出来。别名表与枚举合在一处，是为了让「分红」这个词只有一个答案。
TRADE_TYPE_ALIASES: dict[str, TradeType | NonTradeType] = {
    "分红": TradeType.DIVIDEND,
    "分红派息": TradeType.DIVIDEND,
    "股息": TradeType.DIVIDEND,
    "红利": TradeType.DIVIDEND,
    "红利入账": TradeType.DIVIDEND,
    "派息": TradeType.DIVIDEND,
    "送股": TradeType.BONUS_SHARE,
    "送转股": TradeType.BONUS_SHARE,
    "送股转增": TradeType.BONUS_SHARE,
    "转增": TradeType.BONUS_SHARE,
    "转增股本": TradeType.BONUS_SHARE,
    # 拆股此前不在词表里，一遇到就整批拒绝；它与送转对成本的影响是同一条。
    "拆股": TradeType.BONUS_SHARE,
    "拆分": TradeType.BONUS_SHARE,
    "股份拆分": TradeType.BONUS_SHARE,
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

    - `TradeType`：入账（**还要看这一行给没给出该类需要的数字**，
      见 `cli/commands/import_cmd.py` 的完整性判定）；
    - `NonTradeType`：认得出、不入账，必须逐行报出来；
    - `None`：认不出——那是「这个值非法」，应当整批拒绝，而不是当成不入账
      静默放过。两者的处置相反：前者要用户改文件，后者只要用户知道。
    """
    text = raw.strip()
    try:
        return TradeType(text)
    except ValueError:
        return TRADE_TYPE_ALIASES.get(text)
