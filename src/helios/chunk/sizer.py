# 作者：晨星
"""把 heading-aware 块打包成定长语块，支持 overlap 前缀（ARCH §3.2 / F-7）。"""

from __future__ import annotations

from .splitter import Block


def size_blocks(
    blocks: list[Block], chunk_size: int, overlap: int
) -> list[tuple[str, tuple[str, ...], int, int]]:
    """把段落块贪心打包为不超过 ``chunk_size`` 字符的语块。

    Returns:
        元组列表 ``(text, heading_path, span_start, span_end)``，供 ChunkService 构造 Chunk。
    """
    result: list[tuple[str, tuple[str, ...], int, int]] = []
    cur_parts: list[str] = []
    cur_heading: tuple[str, ...] = ()
    cur_start = 0
    cur_open = False

    for block in blocks:
        projected = sum(len(part) + 1 for part in cur_parts) + len(block.text)
        if cur_open and projected > chunk_size:
            text = "\n".join(cur_parts).strip()
            result.append((text, cur_heading, cur_start, cur_start + len(text)))
            tail = text[-overlap:] if overlap > 0 and len(text) > overlap else (text if overlap > 0 else "")
            cur_parts = [tail] if tail else []
            cur_heading = block.heading_path
            cur_start = block.start
            cur_open = bool(tail)
        cur_parts.append(block.text)
        if not cur_open:
            cur_start = block.start
            cur_open = True
        cur_heading = block.heading_path

    if cur_open:
        text = "\n".join(cur_parts).strip()
        if text:
            result.append((text, cur_heading, cur_start, cur_start + len(text)))
    return result
