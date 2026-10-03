"""CSV 导入测试：表头校验、行号定位、整批原子性，以及认得出但不入账的行。

倒数第二组（`B-27`）锁的是「未入账的行不会被顺手改成静默跳过」：
断言的是**报出来的行号**与**未入账的行数**，不是「命令没报错」。

最后一组（`B-38`）锁的是分红 / 送转真的入账了，以及**缺数字的那一行**不会把
整份对账单拖下水——那是 `B-27` 的教训反过来用一次。
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from holdings.cli.commands.import_cmd import import_cmd
from holdings.exceptions import TradeValidationError
from holdings.models.enums import NonTradeType, TradeType, classify_trade_type
from holdings.portfolio import calculator
from holdings.storage import transaction_dao

HEADER = "symbol,market,trade_date,trade_type,quantity,price\n"

#: 本工具**仍不支持**的非买卖行，覆盖 `NonTradeType` 的全部取值。
#: 分红 / 送转在 B-38 之前也在这张表里，现在它们入账了。
UNSUPPORTED_ROWS = [
    (3, "配股"),
    (4, "银证转账"),
    (5, "利息"),
]


@pytest.fixture
def run_import(tmp_path, monkeypatch):
    """在临时工作目录里写一份对账单并执行导入，返回 (result, 落库交易数)。"""

    def _run(text: str, *extra: str, encoding: str = "utf-8"):
        monkeypatch.chdir(tmp_path)
        csv_file = tmp_path / "in.csv"
        csv_file.write_bytes(text.encode(encoding))
        result = CliRunner().invoke(import_cmd, ["--file", str(csv_file), *extra])
        count = len(transaction_dao.get_all(str(tmp_path / "data" / "holdings.db")))
        return result, count

    return _run


def _position(tmp_path, symbol: str):
    """从临时库里重算持仓。断言的是**落库之后**的数字，不是内存里那份。"""
    db_path = str(tmp_path / "data" / "holdings.db")
    return calculator.compute_positions(transaction_dao.get_all(db_path))[symbol]


def test_valid_csv_imports_all_rows(run_import):
    result, count = run_import(
        HEADER + "NVDA,美股,2025-01-02,BUY,10,100\n" + "TSLA,美股,2025-01-03,BUY,5,200\n"
    )
    assert result.exit_code == 0
    assert count == 2
    assert "识别 2 行，入账 2 笔，未入账 0 行" in result.output


def test_missing_required_column_is_reported(run_import):
    result, count = run_import("symbol,trade_date,trade_type,quantity\nNVDA,2025-01-02,BUY,10\n")
    assert isinstance(result.exception, TradeValidationError)
    assert "缺少必需列" in str(result.exception)
    assert "price" in str(result.exception)
    assert count == 0


def test_bad_row_aborts_whole_import_and_names_the_line(run_import):
    """此前每行各自 commit，坏行之前的行会留在库里。"""
    result, count = run_import(
        HEADER + "NVDA,美股,2025-01-02,BUY,10,100\n" + "TSLA,美股,not-a-date,BUY,5,200\n"
    )
    assert isinstance(result.exception, TradeValidationError)
    assert "第 3 行" in str(result.exception)
    assert "trade_date" in str(result.exception)
    assert count == 0, "整批应当一笔都不写"


def test_invalid_share_count_is_reported_with_line_number(run_import):
    result, count = run_import(HEADER + "NVDA,美股,2025-01-02,BUY,abc,100\n")
    assert isinstance(result.exception, TradeValidationError)
    assert "第 2 行" in str(result.exception)
    assert "quantity" in str(result.exception)
    assert count == 0


def test_oversell_within_csv_is_rejected(run_import):
    result, count = run_import(
        HEADER + "NVDA,美股,2025-01-02,BUY,10,100\n" + "NVDA,美股,2025-01-03,SELL,15,100\n"
    )
    assert isinstance(result.exception, TradeValidationError)
    assert "超过当时持有量" in str(result.exception)
    assert count == 0


def test_fee_column_must_exist(run_import):
    result, count = run_import(HEADER + "NVDA,美股,2025-01-02,BUY,10,100\n", "--fee-column", "佣金")
    assert isinstance(result.exception, TradeValidationError)
    assert "指定的列不存在" in str(result.exception)
    assert count == 0


def test_fee_column_is_applied_when_present(run_import):
    result, count = run_import(
        "symbol,market,trade_date,trade_type,quantity,price,佣金\n"
        "NVDA,美股,2025-01-02,BUY,10,100,7.5\n",
        "--fee-column",
        "佣金",
    )
    assert result.exit_code == 0
    assert count == 1


def test_empty_csv_reports_no_rows(run_import):
    result, count = run_import(HEADER)
    assert result.exit_code == 0
    assert "没有数据行" in result.output
    assert count == 0


# --- 认得出但不入账的行（B-27）------------------------------------------------
#
# 配股 / 银证转账 / 利息这三类行，真实对账单里一定有，但本工具表达不了
# （或与持仓无关）。它们不入账，**必须**逐行报出来。


@pytest.mark.parametrize(
    ("csv_text", "column", "extra"),
    [
        (HEADER + "600519,港股,2025-01-02,BUY,100,10\n", "market", ()),
        (
            "symbol,market,asset_type,trade_date,trade_type,quantity,price\n"
            "600519,A股,fund,2025-01-02,BUY,100,10\n",
            "asset_type",
            (),
        ),
        (HEADER + "600519,A股,2025-01-02,BUY,100,abc\n", "price", ()),
        (
            "symbol,market,trade_date,trade_type,quantity,price,佣金\n"
            "600519,A股,2025-01-02,BUY,100,10,abc\n",
            "佣金",
            ("--fee-column", "佣金"),
        ),
    ],
)
def test_every_bad_column_names_the_line_and_the_column(run_import, csv_text, column, extra):
    """入账的行逐列校验，报错必须同时给出**行号**与**列名**。

    `_row_to_transaction` 的 trade_type 改由调用方传入（B-27），
    其余几列的报错分支随之要确认没被改坏。
    """
    result, count = run_import(csv_text, *extra)

    assert isinstance(result.exception, TradeValidationError)
    assert f"第 2 行 {column} 列" in str(result.exception)
    assert count == 0


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("BUY", TradeType.BUY),
        ("SELL", TradeType.SELL),
        ("FEE", TradeType.FEE),
        ("分红派息", TradeType.DIVIDEND),
        ("红利入账", TradeType.DIVIDEND),
        (" 分红 ", TradeType.DIVIDEND),
        ("送转股", TradeType.BONUS_SHARE),
        ("转增股本", TradeType.BONUS_SHARE),
        ("拆股", TradeType.BONUS_SHARE),
        ("配股缴款", NonTradeType.RIGHTS_ISSUE),
        ("证券转银行", NonTradeType.TRANSFER),
        ("利息归本", NonTradeType.INTEREST),
        ("HODL", None),
        ("", None),
    ],
)
def test_classify_trade_type_has_three_outcomes(raw, expected):
    """三种结果对应三种处置：入账 / 报出来 / 整批拒绝。

    `None` 必须与 `NonTradeType` 分得开——把认不出的值也当成「不入账」放过，
    用户改错了文件却什么都看不到。
    """
    assert classify_trade_type(raw) is expected


def test_every_category_has_a_label_a_reason_and_an_alias():
    """新增一个类型时，漏写标签、原因或别名都会红。

    漏写标签的后果是 `KeyError` 而不是一行说明（用户看到的是一份没入账、
    又没说为什么的对账单）；漏写别名则该类别永远触发不了，等于白加。
    标签尤其容易漏：`TradeType` 的 value 是英文的，直接印到终端上，
    用户对不上自己文件里写的「红利入账」。
    """
    from holdings.cli.commands.import_cmd import (
        _CORPORATE_ACTIONS,
        CATEGORY_LABELS,
        UNPOSTED_REASONS,
    )
    from holdings.models.enums import TRADE_TYPE_ALIASES

    # 「能变成未入账行的类别」= 仍不支持的那几类 + 有完整性判定的公司行为。
    # 两边都是手写的，所以断言的是**两个来源的键集相等**而不是各查一遍。
    assert set(CATEGORY_LABELS) == set(NonTradeType) | set(_CORPORATE_ACTIONS)
    assert set(UNPOSTED_REASONS) == set(NonTradeType)
    # 对账单里的中文写法要能指回某个类别。认得出但不入账的那三类一个都不能漏，
    # 否则它们会掉进「认不出」那一支、把整份对账单拒掉。
    assert set(TRADE_TYPE_ALIASES.values()) >= set(NonTradeType)


def test_every_unsupported_row_is_listed_and_none_is_posted(run_import):
    """一份含全部「仍不支持」类别的样本：逐行列出，库中一笔不多。"""
    result, count = run_import(
        HEADER
        + "600519,A股,2025-01-02,BUY,100,10\n"
        + "".join(
            f"600519,A股,2025-06-{i + 1:02d},{name},0,0\n"
            for i, (_, name) in enumerate(UNSUPPORTED_ROWS)
        )
    )

    assert result.exit_code == 0
    assert count == 1, "未入账的行一笔都不该进库"
    assert "识别 4 行，入账 1 笔，未入账 3 行" in result.output
    for line_no, name in UNSUPPORTED_ROWS:
        assert f"第 {line_no} 行 {name}，未入账" in result.output
    assert result.output.count("未入账：") == len(UNSUPPORTED_ROWS), "每一行都要给出原因"


def test_an_alias_is_reported_with_the_category_it_mapped_to(run_import):
    """用户按自己券商的叫法写的行，要能看到它被归到了哪一类。"""
    result, count = run_import(HEADER + "600519,A股,2025-06-20,配股缴款,0,0\n")

    assert count == 0
    assert "第 2 行 配股缴款（配股），未入账" in result.output


def test_a_corporate_action_row_prints_a_chinese_category(run_import):
    """`TradeType.DIVIDEND` 的 value 是英文的，印出来得是「分红」。

    用户文件里写的是「红利入账」，终端上回一句 `DIVIDEND` 他没法把两件事对上。
    """
    result, _ = run_import(HEADER + "600519,A股,2025-06-20,红利入账,,\n")

    assert "第 2 行 红利入账（分红），未入账" in result.output
    assert "DIVIDEND" not in result.output


def test_an_unsupported_row_needs_no_valid_numbers(run_import):
    """不入账的行不校验数量与价格——它们根本不进账本。"""
    result, count = run_import(HEADER + "600519,A股,2025-06-20,配股,,\n")

    assert result.exit_code == 0
    assert count == 0
    assert "第 2 行 配股，未入账" in result.output


def test_an_unknown_trade_type_still_rejects_the_whole_batch(run_import):
    """认不出的取值仍然是「非法」，与「认识但不入账」区别对待。"""
    result, count = run_import(
        HEADER + "600519,A股,2025-01-02,BUY,100,10\n" + "600519,A股,2025-06-20,HODL,0,0\n"
    )

    assert isinstance(result.exception, TradeValidationError)
    assert "第 3 行 trade_type 列不是合法交易类型：HODL" in str(result.exception)
    assert count == 0, "认不出 = 整批拒绝，一笔都不写"


def test_strict_writes_nothing_when_a_row_cannot_be_posted(run_import):
    """--strict 是「要么全进、要么不进」，不是「先进去再报错」。"""
    result, count = run_import(
        HEADER + "600519,A股,2025-01-02,BUY,100,10\n" + "600519,A股,2025-06-20,配股,0,0\n",
        "--strict",
    )

    assert isinstance(result.exception, TradeValidationError)
    assert "第 3 行 配股，未入账" in result.output
    assert count == 0, "有未入账的行时，连能入账的那笔也不写"


def test_strict_imports_normally_when_every_row_is_postable(run_import):
    """--strict 只在真有未入账的行时改变行为。"""
    result, count = run_import(HEADER + "600519,A股,2025-01-02,BUY,100,10\n", "--strict")

    assert result.exit_code == 0
    assert count == 1
    assert "识别 1 行，入账 1 笔，未入账 0 行" in result.output


# --- 公司行为入账（B-38）------------------------------------------------------
#
# 分红 / 送转从「认得出但不入账」改成入账。它们与买卖一样整批校验，但**没给对
# 数字**的行不能拖垮整份文件：归入未入账逐行报出即可。一份对账单里几百行，
# 其中一行是券商按另一套口径写的，整批拒绝等于这份对账单永远导不进来。


def test_a_dividend_row_is_imported_and_thins_the_cost(run_import, tmp_path):
    """判据：带分红行的对账单能整批导入，成本价随分红下降。

    100 股 @10 成本 1000；每 10 股派 5 元 → 每股 0.5，摊薄后成本价 9.5。
    """
    result, count = run_import(
        HEADER + "600519,A股,2025-01-02,BUY,100,10\n" + "600519,A股,2025-06-20,分红派息,100,0.5\n"
    )

    assert result.exit_code == 0
    assert "识别 2 行，入账 2 笔，未入账 0 行" in result.output
    assert count == 2
    pos = _position(tmp_path, "600519")
    assert pos.quantity == pytest.approx(100)
    assert pos.total_cost == pytest.approx(950)
    assert pos.avg_cost == pytest.approx(9.5)


def test_a_bonus_share_row_adds_shares_without_adding_cost(run_import, tmp_path):
    """判据：十送十之后股数翻倍、总成本不变，成本价折半。"""
    result, count = run_import(
        HEADER + "600519,A股,2025-01-02,BUY,100,10\n" + "600519,A股,2025-06-20,转增,100,0\n"
    )

    assert result.exit_code == 0
    assert count == 2
    pos = _position(tmp_path, "600519")
    assert pos.quantity == pytest.approx(200)
    assert pos.total_cost == pytest.approx(1000)
    assert pos.avg_cost == pytest.approx(5.0)


def test_an_incomplete_corporate_action_row_is_reported_not_rejected(run_import, tmp_path):
    """判据：缺数字的公司行为行归入未入账，**不**让整份对账单失败。

    对账单里这几行常常是空的数量 / 价格（金额在券商那边另一列）。因为一行没有
    持股数就让整份对账单导不进来，比那一行不入账坏得多。
    """
    result, count = run_import(
        HEADER + "600519,A股,2025-01-02,BUY,100,10\n" + "600519,A股,2025-06-20,分红派息,,\n"
    )

    assert result.exit_code == 0, "缺数字不是「非法」，不该整批拒绝"
    assert count == 1, "缺数字的那行不入账，其余照常"
    assert "识别 2 行，入账 1 笔，未入账 1 行" in result.output
    assert "第 3 行 分红派息（分红），未入账" in result.output
    assert "持股数与每股派息" in result.output


@pytest.mark.parametrize(
    ("row", "reason"),
    [
        # 每股派息是金额乘数，为 0 就是一笔 0 元分红——静默入账等于什么也没发生。
        ("分红派息,100,0", "必须大于 0"),
        ("分红派息,0,0.5", "必须大于 0"),
        # 送转不涉及成交金额；对账单把市价填在这一列是常见的，别当成成交价收下。
        ("转增,100,3", "不涉及金额"),
    ],
)
def test_a_corporate_action_row_written_off_caliber_is_reported(run_import, row, reason):
    """数字给了但口径对不上，同样归入未入账——不整批拒绝，也不静默算错。"""
    result, count = run_import(
        HEADER + "600519,A股,2025-01-02,BUY,100,10\n" + f"600519,A股,2025-06-20,{row}\n"
    )

    assert result.exit_code == 0
    assert count == 1
    assert "未入账 1 行" in result.output
    assert reason in result.output


def test_a_non_numeric_corporate_action_number_still_rejects_the_batch(run_import):
    """「没给数字」与「给的不是数字」处置相反，这条边界要钉住。

    没给（单元格是空的）→ 这一行不入账，其余照常导入，用户补上那一格即可；
    给的是一串字母 → 这是「这个值非法」，整批拒绝、退出码 5，要用户改文件。
    两者混为一谈会各错一半：把前者当错误，一份对账单永远导不进来（B-27）；
    把后者当「没给」，用户改错了文件却什么都看不到。
    """
    result, count = run_import(
        HEADER + "600519,A股,2025-01-02,BUY,100,10\n" + "600519,A股,2025-06-20,分红派息,一百,0.5\n"
    )

    assert isinstance(result.exception, TradeValidationError)
    assert "第 3 行 quantity 列" in str(result.exception)
    assert count == 0, "认不出的值 = 整批拒绝，一笔都不写"


def test_strict_aborts_on_an_incomplete_corporate_action_row(run_import):
    """`--strict` 的语义随之收窄：完整的公司行为行不再算未入账。"""
    result, count = run_import(
        HEADER + "600519,A股,2025-01-02,BUY,100,10\n" + "600519,A股,2025-06-20,分红派息,,\n",
        "--strict",
    )

    assert isinstance(result.exception, TradeValidationError)
    assert count == 0


def test_strict_imports_normally_when_every_corporate_action_row_is_complete(run_import):
    result, count = run_import(
        HEADER + "600519,A股,2025-01-02,BUY,100,10\n" + "600519,A股,2025-06-20,分红派息,100,0.5\n",
        "--strict",
    )

    assert result.exit_code == 0
    assert count == 2
    assert "未入账 0 行" in result.output


# --- 券商格式（B-28）----------------------------------------------------------
#
# 用户手里的对账单不是英文表头的 CSV：编码是 GBK、表头是中文、费用拆三列。
# 下面两份夹具是**示例**格式（见 `data/brokers/demo_a.py`），真实券商的解析器
# 等真实样本（BACKLOG B-30）。

DEMO_A_TEXT = (
    "成交日期,证券代码,业务名称,成交数量,成交均价,佣金,印花税,过户费,交易市场\n"
    "2025-01-02,600519,证券买入,100,1500.00,5.00,0.00,0.10,上海\n"
    "2025-06-20,600519,分红派息,0,0,0,0,0,上海\n"
    "2025-03-03,600519,证券卖出,20,1600.00,5.00,1.60,0.02,上海\n"
)

DEMO_B_TEXT = (
    "发生日期,股票代码,业务标志,成交股数,成交价格,手续费,市场\n"
    "2025-01-02,600519,普通买入,100,1500.00,5.10,A股\n"
    "2025-03-03,600519,BUY,10,1510.00,3.00,沪市\n"
)


def test_a_broker_statement_is_recognized_and_imported(run_import):
    """判据：夹具整批导入，走自动识别那条路。

    分红那行仍不入账，但原因变了（B-38）：这一类**支持了**，是这一行没给数字
    ——示例格式的 成交数量 / 成交均价 两列在分红行上是 0，红包金额在券商那边
    另有一列，而这个格式没有映射它。要入账得让解析器把持股数与每股派息翻出来。
    """
    result, count = run_import(DEMO_A_TEXT)

    assert result.exit_code == 0
    assert count == 2, "买入与卖出入账，分红那行缺数字、不入账"
    assert "识别 3 行，入账 2 笔，未入账 1 行" in result.output
    assert "第 3 行 分红派息（分红），未入账" in result.output


def test_the_second_broker_format_also_imports(run_import):
    """判据里的「两个夹具各能整批导入」，第二个。"""
    result, count = run_import(DEMO_B_TEXT)

    assert result.exit_code == 0
    assert count == 2
    assert "识别 2 行，入账 2 笔，未入账 0 行" in result.output


def test_the_broker_option_takes_the_same_path_as_detection(run_import):
    """`--broker` 指定与自动识别必须走到同一处，不是两条实现。"""
    result, count = run_import(DEMO_A_TEXT, "--broker", "demo-a")

    assert result.exit_code == 0
    assert count == 2
    assert "解析格式：示例格式 A" in result.output


def test_the_recognized_format_is_reported(run_import):
    """认成了哪家要说出来——识别本身不报错，不说就没得查。"""
    result, _ = run_import(DEMO_B_TEXT)

    assert "解析格式：示例格式 B" in result.output


def test_an_unfamiliar_header_is_refused_rather_than_guessed(run_import):
    """判据：表头陌生时是「请用 --broker 指定」，不是半批乱数据。"""
    result, count = run_import("交易日期,证券编码,摘要,股数,单价\n2025-01-02,600519,买入,100,10\n")

    assert isinstance(result.exception, TradeValidationError)
    assert "认不出这份对账单的格式" in str(result.exception)
    assert "--broker" in str(result.exception)
    assert count == 0


def test_an_unknown_broker_name_is_refused(run_import):
    result, count = run_import(DEMO_A_TEXT, "--broker", "demo-z")

    assert isinstance(result.exception, TradeValidationError)
    assert "没有名为 demo-z 的对账单格式" in str(result.exception)
    assert count == 0


def test_a_gb18030_statement_is_read(run_import):
    """判据：GB18030 与 UTF-8 各有用例。Windows 上 Excel 另存为就是 GBK。"""
    result, count = run_import(DEMO_A_TEXT, encoding="gb18030")

    assert result.exit_code == 0
    assert count == 2


def test_the_split_fee_columns_end_up_in_the_transaction(run_import, tmp_path):
    """佣金 5.00 + 印花税 0 + 过户费 0.10，一列都不许漏。"""
    run_import(DEMO_A_TEXT)

    txs = transaction_dao.get_all(str(tmp_path / "data" / "holdings.db"))
    buy = next(tx for tx in txs if tx.trade_type is TradeType.BUY)

    assert buy.fee == pytest.approx(5.10)


# --- 资金账号落成组合分组（B-32）------------------------------------------------
#
# 对账单天然带资金账号，而 `portfolio_group` 正好是干这个的。此前一次导入只能
# 给全批指定同一个组，两账号的对账单导进来就分不开了。

ACCOUNT_HEADER = "symbol,market,trade_date,trade_type,quantity,price,account\n"


def _groups(run_import_result, tmp_path) -> dict[str, int]:
    """库里每个组合各几笔——按 `portfolio_group` 数，不按命令输出数。"""
    counts: dict[str, int] = {}
    for tx in transaction_dao.get_all(str(tmp_path / "data" / "holdings.db")):
        counts[tx.portfolio_group] = counts.get(tx.portfolio_group, 0) + 1
    return counts


def test_the_account_column_splits_one_statement_into_several_groups(run_import, tmp_path):
    """判据：一份含两个资金账号的样本，导入后两个 group 各自落得进去。"""
    run_import(
        ACCOUNT_HEADER
        + "600519,A股,2025-01-02,BUY,100,10,A12345\n"
        + "600519,A股,2025-01-03,BUY,100,11,A12345\n"
        + "NVDA,美股,2025-01-04,BUY,10,100,B67890\n"
    )

    assert _groups(None, tmp_path) == {"A12345": 2, "B67890": 1}


def test_the_group_line_is_printed_only_when_there_is_more_than_one(run_import, tmp_path):
    """分散到多个组必须当场说——不然用户按默认分组看会以为账丢了。

    只有一个组时不印：那是常态，每次都印就成了废话（同「重复 0 行」只印一次
    的道理反着来，因为那一个是「真的查过」）。
    """
    split_result, _ = run_import(
        ACCOUNT_HEADER
        + "600519,A股,2025-01-02,BUY,100,10,A12345\n"
        + "NVDA,美股,2025-01-04,BUY,10,100,B67890\n"
    )
    single_result, _ = run_import(
        ACCOUNT_HEADER
        + "600519,A股,2025-01-02,BUY,100,10,A12345\n"
        + "600519,A股,2025-01-03,BUY,100,11,A12345\n",
        "--dedupe",
        "off",
    )

    assert "落组：A12345 1 笔、B67890 1 笔" in split_result.output
    assert "落组" not in single_result.output


def test_the_group_option_only_catches_rows_without_an_account(run_import, tmp_path):
    """账号优先、`--group` 兜底：文件说得比命令行细。

    反过来让 `--group` 压过账号，上面那份两账号的对账单就会静默并成一个组。
    """
    run_import(
        ACCOUNT_HEADER
        + "600519,A股,2025-01-02,BUY,100,10,A12345\n"
        + "NVDA,美股,2025-01-04,BUY,10,100,\n",
        "--group",
        "养老金",
    )

    assert _groups(None, tmp_path) == {"A12345": 1, "养老金": 1}


def test_a_statement_without_an_account_column_stays_in_one_group(run_import, tmp_path):
    """没有账号列时与改动前一样：全批落进 `--group`，一个字都不变。"""
    result, _ = run_import(HEADER + "NVDA,美股,2025-01-02,BUY,10,100\n", "--group", "养老金")

    assert _groups(None, tmp_path) == {"养老金": 1}
    assert "落组" not in result.output


def test_demo_a_maps_its_own_account_column(run_import, tmp_path):
    """券商的列名由解析器映射过来，命令行的代码不认识「资金账号」这四个字。"""
    run_import(
        "成交日期,证券代码,业务名称,成交数量,成交均价,佣金,印花税,过户费,交易市场,资金账号\n"
        "2025-01-02,600519,证券买入,100,1500.00,5.00,0.00,0.10,上海,A12345\n"
    )

    assert _groups(None, tmp_path) == {"A12345": 1}


def test_the_group_breakdown_counts_what_was_actually_written(run_import, tmp_path):
    """`--dedupe skip` 丢掉的行不该还算在里面——否则「落组」与「入账 N 笔」对不上。

    第二份文件里 A12345 那行是重复的、B67890 那行是新的。按拆分时数会是两个组
    （于是印「落组」），按真正写进去的那批数只剩一个组。
    """
    run_import(ACCOUNT_HEADER + "600519,A股,2025-01-02,BUY,100,10,A12345\n")
    result, _ = run_import(
        ACCOUNT_HEADER
        + "600519,A股,2025-01-02,BUY,100,10,A12345\n"
        + "NVDA,美股,2025-01-04,BUY,10,100,B67890\n",
        "--dedupe",
        "skip",
    )

    assert "入账 1 笔" in result.output
    assert "落组" not in result.output, "丢掉重复那行之后只剩一个组，不该再印落组"
    assert _groups(None, tmp_path) == {"A12345": 1, "B67890": 1}
