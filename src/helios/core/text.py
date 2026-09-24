# 作者：晨星
"""文本工具：全角归一化、中英分词、字符 bigram、句子切分（ARCH §4 / F-10）。

硬约束：
    * 源码内绝不出现 emoji / 符号字面量，检测类代码只用 ``ord()`` 码点范围判断（C3 / F-18）；
    * 句号只在**后接空白或结尾**时才切分，正确正则见 :data:`SENTENCE_SPLIT_PATTERN`，
      否则 ``Python 3.10`` 会被误切成两句，抽取式答案会漏关键词（F-10）。
"""

from __future__ import annotations

import re
import unicodedata


#: 句子切分正则：中文句末标点直接切；英文句末标点仅在后接空白或结尾时切（ARCH F-10）。
SENTENCE_SPLIT_PATTERN: str = r"(?<=[。！？])|(?<=[.!?])(?=\s|$)"

_SENTENCE_SPLIT_RE: re.Pattern[str] = re.compile(SENTENCE_SPLIT_PATTERN)

#: 汉字与扩展区码点区间（检测只用 ord 范围，不写字面量）。
CJK_RANGES: tuple[tuple[int, int], ...] = (
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xF900, 0xFAFF),
    (0x20000, 0x2A6DF),
    (0x2A700, 0x2EBEF),
)

#: 全角空格（表意空格）码点。
IDEOGRAPHIC_SPACE: int = 0x3000

#: 拉丁词内字符：ASCII 字母、数字、下划线。
_LATIN_WORD_RE: re.Pattern[str] = re.compile(r"[A-Za-z0-9_]+")


def is_cjk_char(char: str) -> bool:
    """判断单个字符是否为汉字（含扩展区）。"""
    code_point = ord(char)
    return any(low <= code_point <= high for low, high in CJK_RANGES)


def is_space_char(char: str) -> bool:
    """判断单个字符是否为空白（含全角空格）。"""
    return char.isspace() or ord(char) == IDEOGRAPHIC_SPACE


def normalize_text(text: str, lower: bool = False) -> str:
    """全角归一化 + 空白折叠。

    Args:
        text: 原始文本。
        lower: 是否转小写（检索侧常用，哈希侧保持原样以保留大小写信息）。

    Returns:
        归一化后的文本：NFKC 归一、全角空格转半角、连续空白折叠为单空格、去首尾空白。
    """
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", text)
    chars: list[str] = []
    pending_space = False
    for char in normalized:
        if is_space_char(char):
            pending_space = chars != []
            continue
        if pending_space:
            chars.append(" ")
            pending_space = False
        chars.append(char)
    result = "".join(chars)
    return result.lower() if lower else result


def latin_words(text: str) -> list[str]:
    """抽取拉丁文（含数字）词序列，小写化。"""
    return [match.group(0).lower() for match in _LATIN_WORD_RE.finditer(normalize_text(text, lower=True))]


def char_bigrams(text: str, n: int = 2) -> list[str]:
    """对汉字连续段做字符 n-gram（默认 bigram）；单字段退化为单字。

    中文没有空格，按空格切词会丢掉全部语义，因此必须走字符 bigram（ARCH §6）。
    """
    normalized = normalize_text(text)
    grams: list[str] = []
    buffer: list[str] = []
    for char in normalized:
        if is_cjk_char(char):
            buffer.append(char)
            continue
        grams.extend(_flush_bigrams(buffer, n))
        buffer = []
    grams.extend(_flush_bigrams(buffer, n))
    return grams


def _flush_bigrams(buffer: list[str], n: int) -> list[str]:
    """把一个连续汉字段切成 n-gram；不足 n 个字符时退化为单字。"""
    if not buffer:
        return []
    size = max(1, n)
    if len(buffer) < size:
        return ["".join(buffer)]
    return ["".join(buffer[index : index + size]) for index in range(len(buffer) - size + 1)]


def hashing_tokens(text: str) -> list[str]:
    """哈希嵌入用的 token 序列：拉丁词 + 中文字符 bigram。

    返回顺序稳定，保证同输入的哈希向量逐位相等（确定性，T04 判据）。
    """
    return latin_words(text) + char_bigrams(text)


def lexical_tokens(text: str) -> list[str]:
    """词法检索用的 token 序列：拉丁词 + 中文字符 bigram（与哈希侧口径一致）。"""
    return hashing_tokens(text)


def split_sentences(text: str) -> list[str]:
    """按句末标点切分句子（F-10）。

    Examples:
        >>> split_sentences("Python 3.10 发布了。它很快。")
        ['Python 3.10 发布了。', '它很快。']
    """
    if not text:
        return []
    pieces = _SENTENCE_SPLIT_RE.split(normalize_text(text))
    return [piece.strip() for piece in pieces if piece.strip()]


def clip(text: str, limit: int, suffix: str = "") -> str:
    """按字符数截断文本；limit 非正时返回空串。"""
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    keep = max(0, limit - len(suffix))
    return text[:keep] + suffix


def detect_lang(text: str) -> str:
    """按汉字占比粗判语言，返回 ``zh`` 或 ``en``；空文本视为 ``en``。"""
    if not text:
        return "en"
    total = 0
    cjk = 0
    for char in normalize_text(text):
        if char.isspace():
            continue
        total += 1
        if is_cjk_char(char):
            cjk += 1
    if total == 0:
        return "en"
    return "zh" if cjk / total >= 0.2 else "en"
