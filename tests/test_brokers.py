"""对账单解析器：编码探测、格式识别、把各家的写法翻成规范列。

这一层是 `data/`，所以用例直接调函数、不看终端输出；走命令行的那几条
（`--broker`、`--strict`、落库与否）在 `test_import_cmd.py` 里。
"""

from __future__ import annotations

import codecs
from typing import ClassVar

import pytest

from holdings.data import brokers
from holdings.data.brokers.base import BrokerParser
from holdings.exceptions import TradeValidationError

DEMO_A_HEADER = "成交日期,证券代码,业务名称,成交数量,成交均价,佣金,印花税,过户费,交易市场\n"
DEMO_A_BUY = "2025-01-02,600519,证券买入,100,1500.00,5.00,0.00,0.10,上海\n"
DEMO_A_DIVIDEND = "2025-06-20,600519,分红派息,0,0,0,0,0,上海\n"

DEMO_B_HEADER = "发生日期,股票代码,业务标志,成交股数,成交价格,手续费,市场\n"
DEMO_B_BUY = "2025-01-02,600519,普通买入,100,1500.00,5.10,A股\n"

CANONICAL_HEADER = "symbol,market,trade_date,trade_type,quantity,price\n"


def write(tmp_path, text: str, encoding: str = "utf-8", name: str = "in.csv"):
    path = tmp_path / name
    path.write_bytes(text.encode(encoding))
    return str(path)


def header_of(text: str) -> list[str]:
    return [cell.strip() for cell in brokers.read_table(text)[0]]


# ------------------------------------------------------------------ 识别


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (DEMO_A_HEADER + DEMO_A_BUY, "demo-a"),
        (DEMO_B_HEADER + DEMO_B_BUY, "demo-b"),
        (CANONICAL_HEADER + "600519,A股,2025-01-02,BUY,100,10\n", "csv"),
    ],
)
def test_each_registered_format_is_recognized_by_its_header(text, expected):
    """自动识别认出的必须是那一家，不是「随便认一个」。"""
    header = header_of(text)
    assert brokers.detect(header, brokers.read_table(text)[1:]).name == expected


def test_an_unfamiliar_header_is_not_guessed():
    """判据：表头陌生时得到的是「请用 --broker 指定」，而不是半批乱数据。"""
    header = header_of("交易日期,证券编码,摘要,股数,单价\n2025-01-02,600519,买入,100,10\n")

    with pytest.raises(TradeValidationError) as excinfo:
        brokers.detect(header, [])

    assert "认不出" in str(excinfo.value)
    assert "--broker" in str(excinfo.value)
    # 把可选项列出来，用户不用去翻文档就知道能填什么。
    assert "、".join(brokers.broker_names()) in str(excinfo.value)


def test_a_header_that_fits_two_formats_is_not_guessed():
    """命中多个时报错，不取第一个——取第一个就是猜，而猜错是整批数字错。"""
    text = "symbol," + DEMO_A_HEADER + DEMO_A_BUY
    header = header_of(text)

    with pytest.raises(TradeValidationError) as excinfo:
        brokers.detect(header, [])

    assert "同时符合" in str(excinfo.value)
    assert "标准 CSV" in str(excinfo.value)
    assert "示例格式 A" in str(excinfo.value)


@pytest.mark.parametrize("broker", brokers.BROKERS)
def test_every_broker_is_named_and_named_uniquely(broker):
    """名字是 `--broker` 的取值，也是报错里指路用的东西，不能空、也不能重。"""
    assert broker.name and broker.label
    assert brokers.broker_names().count(broker.name) == 1


def test_an_unknown_broker_name_lists_the_available_ones():
    with pytest.raises(TradeValidationError) as excinfo:
        brokers.get_broker("不存在的券商")

    assert "没有名为 不存在的券商 的对账单格式" in str(excinfo.value)
    assert "csv" in str(excinfo.value)


# ------------------------------------------------------------------ 翻译


def test_columns_and_values_are_translated_to_canonical_ones():
    """本家的列名与业务名称都被翻成规范取值，`--broker A` 的那一套到这儿为止。"""
    rows = brokers.DemoA().parse(DEMO_A_HEADER + DEMO_A_BUY)
    row = rows[0]

    assert row.line_no == 2
    assert row.get("symbol") == "600519"
    assert row.get("trade_date") == "2025-01-02"
    assert row.get("trade_type") == "BUY", "证券买入 → BUY"
    assert row.get("market") == "A股", "上海 → A股"
    assert row.get("quantity") == "100"


def test_fee_split_across_columns_is_added_up():
    """佣金 / 印花税 / 过户费三列相加；原样抛一列上去等于把费用算少了。

    断言的是**字符串**：用浮点加 5.00 + 1.60 + 0.02 会得到
    `6.619999999999999`，那粒沙子会被原样存进账本、再进成本价。
    """
    text = DEMO_A_HEADER + "2025-01-02,600519,证券买入,100,1500.00,5.00,1.60,0.02,上海\n"
    row = brokers.DemoA().parse(text)[0]

    assert row.get("fee") == "6.62"
    assert row.fee_source == "佣金/印花税/过户费", "报错时要说清这个数是哪几列来的"


def test_fee_column_overrides_the_formats_own_fee_columns():
    """用户拿 `--fee-column` 指名一列时以他为准：他看的是自己的文件。"""
    text = "成交日期,证券代码,业务名称,成交数量,成交均价,备注费用,佣金\n"
    row = brokers.DemoA().parse(
        text + "2025-01-02,600519,证券买入,100,1500.00,9.99,5.00\n", "备注费用"
    )[0]

    assert row.get("fee") == "9.99"
    assert row.fee_source == "备注费用"


def test_a_blank_fee_component_counts_as_zero():
    """费用列留空是常事（当天没有印花税就空着），不能因此报错。"""
    text = DEMO_A_HEADER + "2025-01-02,600519,证券买入,100,1500.00,5.00,,,上海\n"

    assert float(brokers.DemoA().parse(text)[0].get("fee")) == pytest.approx(5.00)


def test_an_empty_document_has_no_rows():
    """`parse` 是公开接口，单独拿一份空文档调它也不该 IndexError。"""
    assert brokers.DemoA().parse("") == []


def test_a_bad_fee_component_names_its_own_column():
    """三列相加时某一列不是数字，报的是**那一列**，不是笼统的 fee。"""
    text = DEMO_A_HEADER + "2025-01-02,600519,证券买入,100,1500.00,abc,0.00,0.10,上海\n"

    with pytest.raises(TradeValidationError) as excinfo:
        brokers.DemoA().parse(text)

    assert "第 2 行 佣金 列不是合法数字：abc" in str(excinfo.value)


def test_an_unknown_business_name_is_left_alone():
    """本家没映射的名字原样留着：是「认得出但不入账」还是「不认识」由
    `classify_trade_type` 判断，解析器不该替它做这个主。"""
    text = DEMO_A_HEADER + "2025-01-02,600519,担保品划入,100,1500.00,0,0,0,上海\n"

    assert brokers.DemoA().parse(text)[0].get("trade_type") == "担保品划入"


def test_non_trade_names_are_not_translated_by_each_broker():
    """分红 / 送转这些非买卖行所有券商共有，不该让每家重写一遍映射表。"""
    assert brokers.DemoA().parse(DEMO_A_HEADER + DEMO_A_DIVIDEND)[0].get("trade_type") == "分红派息"


def test_a_missing_column_names_the_alias_the_broker_looked_for():
    """指名了券商还缺列，要把「本家叫什么」一起说，否则用户对不上自己的表头。"""
    text = "成交日期,证券代码,业务名称,成交数量,交易市场\n"  # 少了「成交均价」

    with pytest.raises(TradeValidationError) as excinfo:
        brokers.DemoA().parse(text + "2025-01-02,600519,证券买入,100,上海\n")

    assert "缺少必需列 price（本家叫 成交均价）" in str(excinfo.value)


def test_blank_lines_are_skipped_without_shifting_line_numbers():
    """券商导出的尾部常挂空行，那不是数据；而真数据的行号不能被它挤动。"""
    text = DEMO_A_HEADER + "\n" + DEMO_A_BUY + "\n\n"
    rows = brokers.DemoA().parse(text)

    assert len(rows) == 1
    assert rows[0].line_no == 3, "第 2 行是空行，买入行在第 3 行"


def test_rows_are_read_positionally_not_by_column_name():
    """重复的列名不该把值取串。DictReader 在这里会静默取错列。"""
    text = "成交日期,证券代码,业务名称,成交数量,成交均价,成交均价\n"
    row = brokers.DemoA().parse(text + "2025-01-02,600519,证券买入,100,1500.00,9999.00\n")[0]

    assert row.get("price") == "1500.00"


# ------------------------------------------------------------------ 编码


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "gb18030", "utf-16"])
def test_a_statement_is_read_whatever_its_encoding(tmp_path, encoding):
    """判据：UTF-8 与 GB18030 各有用例；BOM 变体一并锁住。"""
    text = DEMO_A_HEADER + DEMO_A_BUY
    path = write(tmp_path, text, encoding)

    statement = brokers.parse_file(path)

    assert statement.broker_label == "示例格式 A"
    assert statement.rows[0].get("symbol") == "600519", "解错了编码中文会变成乱码"


def test_utf8_is_tried_before_gb18030():
    """顺序颠倒过来的后果是**静默**的：GB18030 能把 UTF-8 的字节解成乱码而不报错。"""
    text = "证券代码\n600519\n"
    raw = text.encode("utf-8")

    assert brokers.decode_statement(raw) == text
    # 危险确实存在：GB18030 能把同一串字节「解」出来，只是内容是错的。
    assert raw.decode("gb18030") != text


def test_bytes_that_are_neither_encoding_are_reported(tmp_path):
    path = tmp_path / "broken.csv"
    path.write_bytes(b"\x80\x81\x82\x80\x81\x82")

    with pytest.raises(TradeValidationError) as excinfo:
        brokers.parse_file(str(path))

    assert "读不出内容" in str(excinfo.value)


def test_a_truncated_utf16_file_is_not_guessed_at():
    """BOM 已经声明了编码，解不开就是文件坏了——不回头去猜 GB18030。"""
    raw = codecs.BOM_UTF16_LE + b"\x60\x00\x05"  # 奇数字节，UTF-16 读不出来

    with pytest.raises(TradeValidationError) as excinfo:
        brokers.decode_statement(raw)

    assert "读不出内容" in str(excinfo.value)


def test_an_empty_file_is_reported_as_empty(tmp_path):
    """空文件说「空」，不要说「认不出格式」——它没在冒充别家。"""
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")

    with pytest.raises(TradeValidationError) as excinfo:
        brokers.parse_file(str(path))

    assert "是空的" in str(excinfo.value)


# ------------------------------------------------------------------ 注册表


def test_a_new_broker_needs_only_a_module_and_a_registry_line(monkeypatch, tmp_path):
    """判据：加第三家券商 = 一个新子类 + 注册一行，别处一行都不用改。

    就地造一家「示例格式 C」塞进注册表，识别与整条 `parse_file` 就通了——
    `import_cmd.py` / `fetcher.py` / `base.py` 都没动过。
    """

    class DemoC(BrokerParser):
        name = "demo-c"
        label = "示例格式 C"
        columns: ClassVar[dict[str, tuple[str, ...]]] = {
            "symbol": ("代码",),
            "trade_date": ("日期",),
            "trade_type": ("类型",),
            "quantity": ("数量",),
            "price": ("价格",),
        }
        trade_types: ClassVar[dict[str, str]] = {"买进": "BUY"}

    monkeypatch.setattr(brokers, "BROKERS", (*brokers.BROKERS, DemoC()))
    path = write(tmp_path, "日期,代码,类型,数量,价格\n2025-01-02,600519,买进,100,10\n")

    statement = brokers.parse_file(path)

    assert statement.broker_label == "示例格式 C"
    assert statement.rows[0].get("trade_type") == "BUY"
    assert "demo-c" in brokers.broker_names()
