"""对账单文件的编码探测。

顺序是 **BOM → 试 UTF-8 → 回落 GB18030**，不能颠倒。GB18030 有覆盖全码位的
四字节形式，几乎能解码任意字节序列——先试它，一份 UTF-8 文件会被解成乱码
**而不报错**，用户看到的将是「业务名称不认识」这种查不到根因的报错。
"""

from __future__ import annotations

import codecs

from holdings.exceptions import TradeValidationError

#: 带 BOM 的编码，长的排前面：UTF-32 的 BOM 以 UTF-16 的 BOM 开头，
#: 先匹配 UTF-16 会把一份 UTF-32 文件按 UTF-16 解出满屏的 NUL。
_BOMS: tuple[tuple[bytes, str], ...] = (
    (codecs.BOM_UTF8, "utf-8-sig"),
    (codecs.BOM_UTF32_LE, "utf-32"),
    (codecs.BOM_UTF32_BE, "utf-32"),
    (codecs.BOM_UTF16_LE, "utf-16"),
    (codecs.BOM_UTF16_BE, "utf-16"),
)

#: 没带 BOM 时依次尝试的编码。UTF-8 必须在前，理由见模块开头。
_FALLBACKS: tuple[str, ...] = ("utf-8", "gb18030")


def _try_decode(raw: bytes, encoding: str) -> str | None:
    """解不开就返回 None，让调用方接着试下一种。"""
    try:
        return raw.decode(encoding)
    except UnicodeDecodeError:
        return None


def decode_statement(raw: bytes) -> str:
    """把对账单的字节解成文本。读不出来时抛 `TradeValidationError`。"""
    declared = next((enc for bom, enc in _BOMS if raw.startswith(bom)), None)

    if declared is not None:
        # BOM 已经明说了编码，不再回落到下面的猜测：一份声明摆在那儿，
        # 再去猜只会猜出更离谱的东西（截断的 UTF-16 会被当 GB18030 读成乱码）。
        text = _try_decode(raw, declared)
        if text is not None:
            return text
    else:
        for encoding in _FALLBACKS:
            text = _try_decode(raw, encoding)
            if text is not None:
                return text

    raise TradeValidationError(
        "这份对账单读不出内容：既不是带 BOM 的 UTF-16 / UTF-32，"
        "也不是 UTF-8 或 GB18030；请在 Excel 里另存为「CSV UTF-8」再试"
    )
