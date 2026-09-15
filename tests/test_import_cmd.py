"""CSV 导入测试：表头校验、行号定位与整批原子性。"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from holdings.cli.commands.import_cmd import import_cmd
from holdings.exceptions import TradeValidationError
from holdings.storage import transaction_dao

HEADER = "symbol,market,trade_date,trade_type,quantity,price\n"


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
    assert "已导入 2 笔交易" in result.output


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
