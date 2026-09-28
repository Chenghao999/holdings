"""标的资料（B-31）：取名字 / 资产类型 / 币种，以及它在 `asset_meta` 里的缓存。

不触网：所有数据源都打桩成脚本化的假实现，只断言「走了哪个源、发了几次请求、
库里留下了什么」。判据里最要紧的一条是**取不到时不能报错**——导入不能因为
没网就做不了，所以离线路径与「拿到了」是同等重要的用例。
"""

import sys
import types

import pandas as pd
import pytest

from holdings.data import instrument, resilience, sources
from holdings.data.fetcher import DataSourceUnavailableError, SymbolNotFoundError
from holdings.models.asset_meta import AssetMeta
from holdings.models.enums import AssetType, MarketType
from holdings.services import asset_meta_service
from holdings.storage import asset_meta_dao, db


@pytest.fixture
def no_sleep(monkeypatch):
    """退避不真睡，否则每个失败用例白等 0.5 秒 × 重试次数。"""
    monkeypatch.setattr(sources.time, "sleep", lambda _seconds: None)


def _info(name="贵州茅台", asset_type=AssetType.STOCK, currency="CNY", source="akshare"):
    return instrument.SymbolInfo(
        symbol="600519",
        name=name,
        market=MarketType.A_SHARE,
        asset_type=asset_type,
        currency=currency,
        source=source,
    )


@pytest.fixture
def fake_sources(monkeypatch):
    """把某个市场的源表换成脚本化的假实现，返回调用记录与「装到哪」。

    用法：`calls = fake_sources(MarketType.A_SHARE, {"akshare": [异常或结果, ...]})`
    """
    calls: dict[str, list[str]] = {}

    def _install(market, plan):
        table = {}
        for name, outcomes in plan.items():
            calls.setdefault(name, [])

            def _fake(symbol, _name=name, _outcomes=outcomes):
                calls[_name].append(symbol)
                outcome = _outcomes[min(len(calls[_name]) - 1, len(_outcomes) - 1)]
                if isinstance(outcome, Exception):
                    raise outcome
                return outcome

            table[name] = _fake
        monkeypatch.setattr(instrument, "_SOURCES", {**instrument._SOURCES, market: table})
        return calls

    return _install


# ------------------------------------------------ 取资料本身


def test_a_share_name_and_market_come_back(fake_sources):
    """判据一：给一个代码能取回名称与市场。"""
    fake_sources(MarketType.A_SHARE, {"akshare": [_info()]})

    info = instrument.fetch_instrument("600519", MarketType.A_SHARE)

    assert info.name == "贵州茅台"
    assert info.market == MarketType.A_SHARE
    assert info.source == "akshare"


def test_asset_type_is_taken_from_the_source_not_guessed(fake_sources):
    """资产类型由数据源给出（`quoteType`），不是拿代码前缀猜的。

    猜错的类型会一路走进报表，而用户看不出那是猜的——所以宁可留空。
    """
    fake_sources(
        MarketType.A_SHARE,
        {"akshare": [_info(asset_type=None, source="yfinance")]},
    )

    assert instrument.fetch_instrument("518880", MarketType.A_SHARE).asset_type is None


def test_falls_back_to_the_next_source_in_configured_order(fake_sources, no_sleep, monkeypatch):
    """第一个源认不出这个代码时，按配置顺序交给下一个。

    重试次数压成 0，好让「调了几次」直接对应「走了几个源」——否则默认的
    1 次重试会让每个失败的源都被记成 2 次调用。
    """
    monkeypatch.setattr(resilience, "retry_count", lambda: 0)
    monkeypatch.setattr(
        sources, "priority_for", lambda market, key="priority": ["akshare", "yfinance"]
    )
    calls = fake_sources(
        MarketType.A_SHARE,
        {
            "akshare": [SymbolNotFoundError("这张表里没有 ETF")],
            "yfinance": [_info(name="黄金ETF", asset_type=AssetType.ETF, source="yfinance")],
        },
    )

    info = instrument.fetch_instrument("518880", MarketType.A_SHARE)

    assert calls["akshare"] == ["518880"]
    assert info.name == "黄金ETF"
    assert info.asset_type == AssetType.ETF


def test_a_market_without_sources_says_so(fake_sources):
    """黄金没有「彼此的备份」式的源，所以直接说清它取不到，不去编一个。"""
    with pytest.raises(DataSourceUnavailableError, match="黄金"):
        instrument.fetch_instrument("518880", MarketType.GOLD)


@pytest.fixture
def fake_yfinance(monkeypatch):
    """把 yfinance 换成假的，返回「最近一次问的代码」。"""

    def _install(info, name="yfinance"):
        asked: list[str] = []

        def _ticker(ticker_name):
            asked.append(ticker_name)
            return types.SimpleNamespace(info=info)

        monkeypatch.setitem(sys.modules, name, types.SimpleNamespace(Ticker=_ticker))
        return asked

    return _install


def test_a_share_uses_the_same_exchange_suffix_rule_as_the_price_fetcher(fake_yfinance):
    """`.SS` / `.SZ` 的规则必须与取价那边一致，否则同一个代码两边取到不同的标的。"""
    asked = fake_yfinance({"shortName": "贵州茅台", "quoteType": "EQUITY", "currency": "CNY"})

    info = instrument._a_share_from_yfinance("600519")

    assert asked == ["600519.SS"]
    assert info.market == MarketType.A_SHARE
    assert info.asset_type == AssetType.STOCK


def test_a_shenzhen_code_gets_the_sz_suffix(fake_yfinance):
    asked = fake_yfinance({"longName": "某深市股", "quoteType": "EQUITY", "currency": "CNY"})

    instrument._a_share_from_yfinance("000001")

    assert asked == ["000001.SZ"]


def test_a_source_without_a_name_is_a_symbol_not_found(fake_yfinance):
    """yfinance 查不到时 `info` 是空的——那是「没这个标的」，要交给下一个源。"""
    fake_yfinance({})

    with pytest.raises(SymbolNotFoundError):
        instrument._us_from_yfinance("NOSUCH")


def test_currency_falls_back_to_the_market_default(fake_yfinance):
    """源没给币种时用市场默认值，而不是留空——空币种会让汇总口径失去依据。"""
    fake_yfinance({"shortName": "某美股", "quoteType": "EQUITY"})

    assert instrument._us_from_yfinance("AAPL").currency == "USD"


def test_akshare_reads_the_name_column(tmp_path, monkeypatch):
    """akshare 那一列叫「名称」，映射错了取回来的会是数字或空。"""
    monkeypatch.setitem(
        sys.modules,
        "akshare",
        types.SimpleNamespace(
            stock_zh_a_spot_em=lambda: pd.DataFrame(
                {"代码": ["600519", "000001"], "名称": ["贵州茅台", "平安银行"]}
            )
        ),
    )

    info = instrument._a_share_from_akshare("000001")

    assert info.name == "平安银行"
    assert info.asset_type == AssetType.STOCK, "这张表只有个股，找到了就说明是股票"


def test_akshare_has_no_etf_row_so_the_chain_moves_on(monkeypatch):
    """ETF 不在 `stock_zh_a_spot_em` 里，这里必须抛出而不是拿个空名字糊弄过去。"""
    monkeypatch.setitem(
        sys.modules,
        "akshare",
        types.SimpleNamespace(
            stock_zh_a_spot_em=lambda: pd.DataFrame({"代码": ["600519"], "名称": ["贵州茅台"]})
        ),
    )

    with pytest.raises(SymbolNotFoundError, match="518880"):
        instrument._a_share_from_akshare("518880")


@pytest.mark.parametrize(
    ("module_name", "call"),
    [
        pytest.param("akshare", lambda: instrument._a_share_from_akshare("600519"), id="akshare"),
        pytest.param("yfinance", lambda: instrument._us_from_yfinance("AAPL"), id="yfinance"),
    ],
)
def test_a_missing_optional_dependency_is_reported_as_such(monkeypatch, module_name, call):
    """没装的可选依赖要报「没装」，不能糊成「数据源不可用」——两者的修法不同。"""
    monkeypatch.setitem(sys.modules, module_name, None)

    with pytest.raises(DataSourceUnavailableError, match="未安装"):
        call()


def test_unknown_quote_type_is_left_empty(fake_yfinance):
    """yfinance 认不出的资产类型（指数、期货……）留空，不硬塞成 stock。"""
    fake_yfinance({"shortName": "某指数", "quoteType": "INDEX", "currency": "USD"})

    info = instrument._us_from_yfinance("^GSPC")

    assert info.name == "某指数"
    assert info.asset_type is None


# ------------------------------------------------ 缓存（判据二）


def test_second_lookup_uses_the_cache_and_does_not_ask_again(db_path, fake_sources, no_sleep):
    """判据二：第二次取同一个代码走缓存、不发请求。"""
    calls = fake_sources(MarketType.A_SHARE, {"akshare": [_info()]})

    first = asset_meta_service.lookup(db_path, "600519", MarketType.A_SHARE)
    second = asset_meta_service.lookup(db_path, "600519", MarketType.A_SHARE)

    assert calls["akshare"] == ["600519"], "第二次不该再问一次数据源"
    assert first is not None and second is not None
    assert second.name == "贵州茅台"
    assert second.asset_type == AssetType.STOCK


def test_expired_cache_is_asked_again(db_path, fake_sources, no_sleep):
    """ttl 一过就得重新取——否则名称改了永远不会更新。"""
    calls = fake_sources(MarketType.A_SHARE, {"akshare": [_info()]})

    asset_meta_service.lookup(db_path, "600519", MarketType.A_SHARE, ttl_seconds=0)
    asset_meta_service.lookup(db_path, "600519", MarketType.A_SHARE, ttl_seconds=0)

    assert len(calls["akshare"]) == 2


def test_ttl_comes_from_the_config(tmp_path, db_path, fake_sources, no_sleep, monkeypatch):
    """默认的 ttl 不写死在代码里，读 `data_sources.instrument_ttl_seconds`。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text(
        "data_sources:\n  instrument_ttl_seconds: 0\n", encoding="utf-8"
    )
    calls = fake_sources(MarketType.A_SHARE, {"akshare": [_info()]})

    asset_meta_service.lookup(db_path, "600519", MarketType.A_SHARE)
    asset_meta_service.lookup(db_path, "600519", MarketType.A_SHARE)

    assert len(calls["akshare"]) == 2, "ttl 配成 0 就该每次都去取"


def test_ttl_falls_back_when_the_config_is_unusable(tmp_path, monkeypatch):
    """配置坏了不该让「查个名字」变成异常——如实报配置错误是别处的职责。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text("data_sources: [这不是映射]\n", encoding="utf-8")

    assert asset_meta_service.instrument_ttl_seconds() > 0


def test_a_row_without_a_name_is_not_a_cache_hit(db_path, fake_sources, no_sleep):
    """手工只填过年化管理费率的行不算「有新资料」，仍然要去取一次名字。

    否则「我先用 meta 记了费率」会让这条代码永远取不到名称。
    """
    asset_meta_dao.upsert(db_path, AssetMeta(symbol="600519", annual_management_fee=0.5))
    calls = fake_sources(MarketType.A_SHARE, {"akshare": [_info()]})

    result = asset_meta_service.lookup(db_path, "600519", MarketType.A_SHARE)

    assert calls["akshare"] == ["600519"]
    assert result.name == "贵州茅台"


def test_caching_does_not_wipe_the_hand_entered_fee(db_path, fake_sources, no_sleep):
    """`annual_management_fee` 只有用户填得出来，不能被一次「查到了名字」抹掉。"""
    asset_meta_dao.upsert(db_path, AssetMeta(symbol="600519", annual_management_fee=0.5))
    fake_sources(MarketType.A_SHARE, {"akshare": [_info()]})

    asset_meta_service.lookup(db_path, "600519", MarketType.A_SHARE)

    stored = asset_meta_dao.get(db_path, "600519")
    assert stored.name == "贵州茅台"
    assert stored.annual_management_fee == 0.5, "取名字不该动费用"


def test_cache_is_written_to_asset_meta(db_path, fake_sources, no_sleep):
    """落库的是 `asset_meta`，不是另开一张表。"""
    fake_sources(MarketType.A_SHARE, {"akshare": [_info()]})

    asset_meta_service.lookup(db_path, "600519", MarketType.A_SHARE)

    with db.connect(db_path) as conn:
        row = conn.execute("SELECT * FROM asset_meta WHERE symbol = '600519'").fetchone()
    assert (row["name"], row["market"], row["asset_type"], row["currency"]) == (
        "贵州茅台",
        "A股",
        "stock",
        "CNY",
    )


# ------------------------------------------------ 取不到（判据一的后半句）


@pytest.mark.parametrize(
    "failure",
    [
        DataSourceUnavailableError("没网"),
        SymbolNotFoundError("查无此代码"),
    ],
)
def test_a_failed_lookup_is_not_an_error(db_path, fake_sources, no_sleep, failure):
    """判据一的后半句：离线或取不到时**不报错，只是留空**。

    导入不该因为没网就做不了——取不到名字是一件可以稍后再补的事，
    不是一件该让整批账写不进去的事。
    """
    fake_sources(MarketType.A_SHARE, {"akshare": [failure]})

    assert asset_meta_service.lookup(db_path, "600519", MarketType.A_SHARE) is None


def test_a_failed_lookup_keeps_what_was_already_known(db_path, fake_sources, no_sleep):
    """取不到时也要把手上的那条还回去，而不是把已缓存的名字一并丢掉。"""
    asset_meta_dao.upsert(db_path, AssetMeta(symbol="600519", name="贵州茅台", currency="CNY"))
    fake_sources(MarketType.A_SHARE, {"akshare": [DataSourceUnavailableError("没网")]})

    result = asset_meta_service.lookup(db_path, "600519", MarketType.A_SHARE, ttl_seconds=0)

    assert result is not None
    assert result.name == "贵州茅台"


def test_lookup_only_swallows_the_known_failures(db_path, monkeypatch):
    """只吞「取不到」，不吞别的错——否则真出 bug 时会安静地少一半数据。

    **注意这里打桩的是 `fetch_instrument` 而不是某个数据源**：降级循环
    （`sources.fetch_with_fallback`）故意捕获所有异常，一个源自己写崩了也会被
    它包成 `DataSourceUnavailableError`——那是取价的既定契约（网络库抛什么的
    都有），不是 `lookup` 该改的事。所以「不吞代码 bug」这条只能在 `lookup`
    这一层守，也就只能在这一层测。
    """
    monkeypatch.setattr(
        asset_meta_service.instrument,
        "fetch_instrument",
        lambda symbol, market: (_ for _ in ()).throw(TypeError("签名对不上")),
    )

    with pytest.raises(TypeError):
        asset_meta_service.lookup(db_path, "600519", MarketType.A_SHARE)


# ------------------------------------------------ 加一个源（判据三）


def test_a_new_source_is_one_function_plus_one_config_line(db_path, no_sleep, monkeypatch):
    """判据三：加一个新来源只改配置与一个模块，降级逻辑不动。

    这里真的加一个第三来源（一个函数 + 配置里一个名字），断言它按顺序被走到，
    而 `sources.fetch_with_fallback` 一个字都没改。
    """

    def _from_exchange(symbol):
        return instrument.SymbolInfo(
            symbol=symbol, name="从新来源拿到", market=MarketType.A_SHARE, source="exchange"
        )

    monkeypatch.setattr(
        instrument,
        "_SOURCES",
        {**instrument._SOURCES, MarketType.A_SHARE: {"exchange": _from_exchange}},
    )
    monkeypatch.setattr(sources, "priority_for", lambda market, key="priority": ["exchange"])

    info = instrument.fetch_instrument("600519", MarketType.A_SHARE)

    assert info.name == "从新来源拿到"


def test_a_configured_source_that_is_not_implemented_is_skipped(
    fake_sources, no_sleep, monkeypatch
):
    """配置里列了但模块里没有的源跳过，不报错——上游库的能力边界不该由用户来记。"""
    monkeypatch.setattr(
        sources, "priority_for", lambda market, key="priority": ["不存在的源", "akshare"]
    )
    fake_sources(MarketType.A_SHARE, {"akshare": [_info()]})

    assert instrument.fetch_instrument("600519", MarketType.A_SHARE).name == "贵州茅台"


def test_instrument_priority_is_a_separate_knob_from_price_priority(tmp_path, monkeypatch):
    """取价与取资料各读各的配置项：能报价的源不一定知道这标的叫什么。"""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text(
        "data_sources:\n"
        "  priority:\n"
        "    A股: [akshare]\n"
        "  instrument_priority:\n"
        "    A股: [yfinance]\n",
        encoding="utf-8",
    )

    assert sources.priority_for(MarketType.A_SHARE) == ["akshare"]
    assert sources.priority_for(MarketType.A_SHARE, sources.INSTRUMENT_PRIORITY_KEY) == ["yfinance"]
