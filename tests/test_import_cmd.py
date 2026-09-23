"""CSV 导入测试：表头校验、行号定位、整批原子性，以及认得出但不入账的行。

最后一组（`B-27`）锁的是「未入账的行不会被顺手改成静默跳过」：
断言的是**报出来的行号**与**未入账的行数**，不是「命令没报错」。
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from holdings.cli.commands.import_cmd import import_cmd
from holdings.exceptions import TradeValidationError
from holdings.models.enums import NonTradeType, TradeType, classify_trade_type
from holdings.storage import transaction_dao

HEADER = "symbol,market,trade_date,trade_type,quantity,price\n"

#: 五类非买卖行，覆盖 `NonTradeType` 的全部取值。
FIVE_NON_TRADE_ROWS = [
    (3, "分红派息"),
    (4, "送股转增"),
    (5, "配股"),
    (6, "银证转账"),
    (7, "利息"),
]


@pytest.fixture
def run_import(tmp_path, monkeypatch):
    """在临时工作目录里写一个 CSV 并执行导入，返回 (result, 落库交易数)。"""

    def _run(csv_text: str, *extra: str):
        monkeypatch.chdir(tmp_path)
        csv_file = tmp_path / "in.csv"
        csv_file.write_text(csv_text, encoding="utf-8")
        result = CliRunner().invoke(import_cmd, ["--file", str(csv_file), *extra])
        count = len(transaction_dao.get_all(str(tmp_path / "data" / "holdings.db")))
        return result, count

    return _run


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
# 分红 / 送转 / 配股 / 银证转账 / 利息这五类行，真实对账单里一定有，
# 但本工具表达不了（或与持仓无关）。它们不入账，**必须**逐行报出来。


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
        ("分红派息", NonTradeType.DIVIDEND),
        ("红利入账", NonTradeType.DIVIDEND),
        ("送转股", NonTradeType.BONUS_SHARE),
        ("配股缴款", NonTradeType.RIGHTS_ISSUE),
        ("证券转银行", NonTradeType.TRANSFER),
        ("利息归本", NonTradeType.INTEREST),
        (" 分红 ", NonTradeType.DIVIDEND),
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


def test_every_non_trade_category_has_a_reason_and_an_alias():
    """新增一类非买卖行时，漏写原因或漏写别名都会红。

    漏写原因的后果是 `KeyError` 而不是一句说明（用户看到的是一份没入账、
    又没说为什么的对账单）；漏写别名则该类别永远触发不了，等于白加。
    """
    from holdings.cli.commands.import_cmd import UNPOSTED_REASONS
    from holdings.models.enums import NON_TRADE_ALIASES

    assert set(UNPOSTED_REASONS) == set(NonTradeType)
    assert set(NON_TRADE_ALIASES.values()) == set(NonTradeType)


def test_all_five_non_trade_rows_are_listed_and_none_is_posted(run_import):
    """一份含全部 5 类非买卖行的样本：逐行列出，库中一笔不多。"""
    result, count = run_import(
        HEADER
        + "600519,A股,2025-01-02,BUY,100,10\n"
        + "".join(
            f"600519,A股,2025-06-0{i},{name},0,0\n"
            for i, (_, name) in enumerate(FIVE_NON_TRADE_ROWS, 1)
        )
    )

    assert result.exit_code == 0
    assert count == 1, "未入账的行一笔都不该进库"
    assert "识别 6 行，入账 1 笔，未入账 5 行" in result.output
    for line_no, name in FIVE_NON_TRADE_ROWS:
        assert f"第 {line_no} 行 {name}，未入账" in result.output
    assert result.output.count("未入账：") == len(FIVE_NON_TRADE_ROWS), "每一行都要给出去原因"


def test_an_alias_is_reported_with_the_category_it_mapped_to(run_import):
    """用户按自己券商的叫法写的行，要能看到它被归到了哪一类。"""
    result, count = run_import(HEADER + "600519,A股,2025-06-20,红利入账,0,0\n")

    assert count == 0
    assert "第 2 行 红利入账（分红派息），未入账" in result.output


def test_a_non_trade_row_needs_no_valid_numbers(run_import):
    """不入账的行不校验数量与价格——它们根本不进账本。

    对账单里分红行常常是空的数量/价格；因为「分红行没有数量」而整批失败，
    等于让一份正确的对账单永远导不进来。
    """
    result, count = run_import(HEADER + "600519,A股,2025-06-20,分红派息,,\n")

    assert result.exit_code == 0
    assert count == 0
    assert "第 2 行 分红派息，未入账" in result.output


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
        HEADER + "600519,A股,2025-01-02,BUY,100,10\n" + "600519,A股,2025-06-20,分红派息,0,0\n",
        "--strict",
    )

    assert isinstance(result.exception, TradeValidationError)
    assert "第 3 行 分红派息，未入账" in result.output
    assert count == 0, "有未入账的行时，连能入账的那笔也不写"


def test_strict_imports_normally_when_every_row_is_postable(run_import):
    """--strict 只在真有未入账的行时改变行为。"""
    result, count = run_import(HEADER + "600519,A股,2025-01-02,BUY,100,10\n", "--strict")

    assert result.exit_code == 0
    assert count == 1
    assert "识别 1 行，入账 1 笔，未入账 0 行" in result.output
