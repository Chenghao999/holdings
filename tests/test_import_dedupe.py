"""导入幂等（B-29）：同一份文件导两遍，账不该翻倍。

判据是「第二次 0 笔入库 + 报出重复的行号」，所以下面断言的是**库中笔数**与
**报出来的行号**，不是「命令没报错」——报了错却照样写进去，正是这一项要防的。

用的都是通用 CSV（`标准 CSV` 那一家），因为查重是 `import` 的事、与格式无关；
另有一条用例走券商格式，确认它同样受益。
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from holdings.cli.commands.import_cmd import import_cmd
from holdings.exceptions import TradeValidationError
from holdings.storage import transaction_dao

HEADER = "symbol,market,trade_date,trade_type,quantity,price\n"
ONE_BUY = "600519,A股,2025-01-02,BUY,100,1500.00\n"
ANOTHER_BUY = "600519,A股,2025-04-01,BUY,10,1550.00\n"

DEMO_A_STATEMENT = (
    "成交日期,证券代码,业务名称,成交数量,成交均价,佣金,印花税,过户费,交易市场\n"
    "2025-01-02,600519,证券买入,100,1500.00,5.00,0.00,0.10,上海\n"
)


@pytest.fixture
def run_import(tmp_path, monkeypatch):
    """写一份对账单并导入，返回 (result, 库中笔数)。同一个目录可以连着调多次。"""
    monkeypatch.chdir(tmp_path)

    def _run(text: str, *extra: str, name: str = "in.csv"):
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        result = CliRunner().invoke(import_cmd, ["--file", str(path), *extra])
        return result, _count(tmp_path)

    return _run


def _count(tmp_path) -> int:
    return len(transaction_dao.get_all(str(tmp_path / "data" / "holdings.db")))


def test_importing_the_same_file_twice_writes_nothing_the_second_time(run_import):
    """判据：第二次 0 笔入库。"""
    text = HEADER + ONE_BUY

    _, after_first = run_import(text)
    _, after_second = run_import(text)

    assert after_first == 1
    assert after_second == 1, "第二次一笔都不该写"


def test_the_second_run_names_the_lines_that_repeat(run_import):
    """判据：指出重复的行号——用户要照着它回文件里核。"""
    text = HEADER + ONE_BUY + ANOTHER_BUY
    run_import(text)

    result, _ = run_import(text)

    assert isinstance(result.exception, TradeValidationError)
    assert "  第 2 行重复：与库里已有的 #1 是同一笔" in result.output
    assert "  第 3 行重复：与库里已有的 #2 是同一笔" in result.output
    assert "第 2、3 行" in str(result.exception)
    assert "未写入任何数据" in str(result.exception)


def test_a_monthly_export_with_an_overlap_imports_only_the_new_rows(run_import):
    """逐月补充导出：本月文件含上月最后几笔，重复的只有那几笔。"""
    run_import(HEADER + ONE_BUY)

    result, count = run_import(HEADER + ONE_BUY + ANOTHER_BUY, "--dedupe", "skip")

    assert result.exit_code == 0
    assert count == 2, "重叠的那笔跳过，新的那笔照写"
    assert "第 2 行重复" in result.output
    assert "识别 2 行，入账 1 笔，未入账 0 行，重复 1 行" in result.output


def test_dedupe_off_lets_the_same_file_through(run_import):
    """同一天同价同费的两笔真实成交需要这条路，否则它们永远导不进来。

    代价是账翻倍，所以它必须是用户明写的选项，不能是默认。
    """
    run_import(HEADER + ONE_BUY)

    result, count = run_import(HEADER + ONE_BUY, "--dedupe", "off")

    assert result.exit_code == 0
    assert count == 2
    assert "重复" not in result.output, "没查就不要报一个数"


def test_a_repeat_inside_one_file_is_reported_too(run_import):
    """文件内部重复（有些券商的导出自带）同样不能静默写两遍。"""
    result, count = run_import(HEADER + ONE_BUY + ONE_BUY)

    assert isinstance(result.exception, TradeValidationError)
    assert "  第 3 行重复：与第 2 行是同一笔" in result.output
    assert count == 0


def test_the_summary_says_how_many_repeats_were_found(run_import):
    """「重复 0 行」是被数出来的，不是没数——与「未入账 0 行」同理。"""
    result, _ = run_import(HEADER + ONE_BUY)

    assert "识别 1 行，入账 1 笔，未入账 0 行，重复 0 行" in result.output


def test_a_broker_statement_is_idempotent_too(run_import):
    """判据：通用 CSV 之外，券商格式那条路同样受益。"""
    run_import(DEMO_A_STATEMENT)

    result, count = run_import(DEMO_A_STATEMENT)

    assert isinstance(result.exception, TradeValidationError)
    assert count == 1


def test_the_source_column_records_which_format_it_came_from(run_import, tmp_path):
    """来源要落库：判重、以及「这批数字是哪来的」都得靠它。"""
    run_import(DEMO_A_STATEMENT)

    tx = transaction_dao.get_all(str(tmp_path / "data" / "holdings.db"))[0]

    assert tx.source == "demo-a", "存的是格式标识（--broker 的取值），不是人话名字"


def test_a_row_with_an_external_id_is_matched_by_it(run_import, tmp_path):
    """有流水号时按流水号判重：指纹分不开的那两笔，流水号分得开。"""
    header = HEADER.rstrip("\n") + ",external_id\n"
    row = "600519,A股,2025-01-02,BUY,100,1500.00,HT-1\n"
    run_import(header + row)

    result, count = run_import(header + row)

    assert isinstance(result.exception, TradeValidationError)
    assert count == 1
    assert transaction_dao.get_all(str(tmp_path / "data" / "holdings.db"))[0].external_id == "HT-1"
