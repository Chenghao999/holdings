"""资产基础信息服务：标的名称、币种与年化管理费率的读写。

CLI 经由本模块访问 `asset_meta_dao`（架构铁律 3）。
"""

from __future__ import annotations

from holdings.data import instrument
from holdings.exceptions import HoldingsError
from holdings.models.asset_meta import AssetMeta
from holdings.models.enums import MarketType
from holdings.storage import asset_meta_dao


def record(db_path: str, meta: AssetMeta) -> None:
    """写入或覆盖一条基础信息（`symbol` 是主键）。"""
    asset_meta_dao.upsert(db_path, meta)


def get(db_path: str, symbol: str) -> AssetMeta | None:
    """按代码取一条；没有记录时返回 `None`。"""
    return asset_meta_dao.get(db_path, symbol)


def remove(db_path: str, symbol: str) -> bool:
    """按代码删除，返回是否真的删掉了一条。"""
    return asset_meta_dao.delete(db_path, symbol)


def lookup(
    db_path: str,
    symbol: str,
    market: MarketType | None = None,
    ttl_seconds: int | None = None,
) -> AssetMeta | None:
    """取一个标的的资料，**先看缓存、再联网，取不到就返回 None**。

    这条路径存在的意义是给导入补上名称与市场，所以它对失败的态度与 `sync`
    相反：`sync` 取不到价是一件要报出来的事，而**导入不该因为没网就做不了**。
    取不到不是错误，是「这个名字暂时不知道」——返回 `None`，让人照常记账。

    `market` 不知道时传 `None`（对账单里常常只有代码），此时按
    `instrument.market_candidates` 的形状顺序逐个试，**第一个答上来的为准**：
    落库的市场是数据源说的，形状只决定先问谁。

    缓存走 `asset_meta`：资料一年也不会变，每次导入都联网问一遍是白问。
    写缓存时**保留已有的年化管理费率**——那份数据只有用户手工填得出来，
    不该被一次「我查到了名字」抹掉。
    """
    existing = asset_meta_dao.get(db_path, symbol)
    ttl = instrument_ttl_seconds() if ttl_seconds is None else ttl_seconds
    if asset_meta_dao.is_fresh(db_path, symbol, ttl):
        return existing

    # 取不到就用手上这条（可能为空）。**只捕获已知异常**：数据源不可用、
    # 编码、网络这些都在 HoldingsError 之下；真出了别的错（代码 bug），
    # 那不该被「没网也一样」吞掉。
    info = _ask_each_market(symbol, market)
    if info is None:
        return existing

    merged = AssetMeta(
        symbol=symbol,
        name=info.name,
        market=info.market.value if info.market else (existing.market if existing else None),
        asset_type=info.asset_type,
        currency=info.currency,
        annual_management_fee=existing.annual_management_fee if existing else 0.0,
    )
    asset_meta_dao.upsert(db_path, merged)
    return merged


def _ask_each_market(symbol: str, market: MarketType | None) -> instrument.SymbolInfo | None:
    """逐个候选市场去问，**第一个答上来的为准**；都问不到返回 None。

    给定了市场就只问那一个：对账单自己写了市场，它比按代码形状排的顺序准。

    一个市场内部还有自己的降级链（A 股是 akshare → yfinance），所以「这个市场
    的源都没装」不会在这里被误判成「没这个标的」——链子会走到下一个源。
    """
    for candidate in [market] if market else instrument.market_candidates(symbol):
        try:
            info = instrument.fetch_instrument(symbol, candidate)
        except (HoldingsError, OSError):
            continue  # 换个市场再问；失败原因对调用方无用，它只关心「有没有拿到」
        return info
    return None


def instrument_ttl_seconds() -> int:
    """资料缓存的有效期，读配置（`data_sources.instrument_ttl_seconds`）。"""
    from holdings.utils.config import load_config

    try:
        return load_config().instrument_ttl_seconds
    except (HoldingsError, OSError):
        from holdings.utils.config import DEFAULT_CONFIG

        return int(DEFAULT_CONFIG["data_sources"]["instrument_ttl_seconds"])


def fee_rate_total(db_path: str, symbols: list[str]) -> float:
    """给定标的的年化管理费率合计（百分数）。

    只为报表展示——**不参与任何成本计算**。真实费用靠 `transactions.fee`
    逐笔记录，这里只是把「你填过的费率加起来是多少」如实报出来。
    """
    wanted = set(symbols)
    return sum(
        m.annual_management_fee for m in asset_meta_dao.get_all(db_path) if m.symbol in wanted
    )
