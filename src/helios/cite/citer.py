# 作者：晨星
"""从答案文本与已用 chunk 构造可回溯引用（ARCH §7 / T08 / P0-5）。

先逐句对齐答案与 chunk 原文，命中则记录精确 span；未命中则回退到 chunk 首段快照。
"""

from __future__ import annotations

from ..core.text import split_sentences
from ..core.types import Chunk, Citation


def build_citations(
    answer_text: str,
    chunks: list[Chunk],
    scores: dict[str, float] | None = None,
    top_n: int = 5,
) -> tuple[Citation, ...]:
    """为答案构造至多 ``top_n`` 条引用。"""
    sentences = split_sentences(answer_text)
    citations: list[Citation] = []
    scores = scores or {}
    for idx, ch in enumerate(chunks[:top_n]):
        span = (0, min(200, len(ch.text)))
        quote = ch.text[: min(200, len(ch.text))]
        for sentence in sentences:
            needle = sentence.strip()
            if len(needle) < 4:
                continue
            pos = ch.text.find(needle)
            if 0 <= pos < len(ch.text):
                span = (pos, pos + len(needle))
                quote = needle
                break
        citations.append(
            Citation(
                citation_id=f"c{idx:02d}",
                chunk_id=ch.chunk_id,
                doc_id=ch.doc_id,
                span_start=span[0],
                span_end=span[1],
                quote=quote,
                score=float(scores.get(ch.chunk_id, 0.0)),
            )
        )
    return tuple(citations)
