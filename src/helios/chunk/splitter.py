# 作者：晨星
"""Heading-aware 块切分：标题行单独成块、起始快照 heading_path（ARCH F-7）。

标题栈按 ``#`` 数量维护层级；每个内容段落快照当前标题路径，供 chunk 回溯上下文。
"""

from __future__ import annotations

import dataclasses
import re


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


@dataclasses.dataclass
class Block:
    """一个待打包的原始块：文本 + 标题路径 + 在原文中的字符区间。"""

    text: str
    heading_path: tuple[str, ...] = ()
    start: int = 0
    end: int = 0


def _is_heading(line: str) -> tuple[bool, int, str]:
    match = _HEADING_RE.match(line.strip())
    if not match:
        return False, 0, ""
    level = len(match.group(1))
    title = match.group(2).strip()
    return True, level, title


def split_blocks(text: str) -> list[Block]:
    """把文档切成带标题路径快照的段落块（按空行分段，标题单独成块）。"""
    lines = text.split("\n")
    blocks: list[Block] = []
    stack: list[tuple[int, str]] = []
    para: list[str] = []

    def flush_para() -> None:
        if not para:
            return
        body = "\n".join(para).strip()
        if body:
            start = max(0, text.find(para[0]))
            blocks.append(
                Block(text=body, heading_path=tuple(t for _, t in stack), start=start, end=start + len(body))
            )
        para.clear()

    for line in lines:
        stripped = line.strip()
        is_heading, level, title = _is_heading(stripped)
        if is_heading:
            flush_para()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            path = tuple(t for _, t in stack)
            start = max(0, text.find(stripped))
            blocks.append(Block(text=title, heading_path=path, start=start, end=start + len(stripped)))
            continue
        if stripped == "":
            flush_para()
            continue
        if not para:
            para.append(line)
    flush_para()
    return blocks
