# 作者：晨星
"""词法重排：以 query-chunk 词法重叠（Jaccard）重排（offline 默认重排器，ARCH §7 / T08）。"""

from __future__ import annotations

from typing import Any

from ..core.text import lexical_tokens
from ..core.types import Chunk, ScoredChunk


class LexicalReranker:
    """用 query 与 chunk 的词法 Jaccard 相似度重排。"""

    def __init__(self, config: Any | None = None) -> None:
        self._name = "lexical"

    def rerank(self, query: str, chunks: list[Chunk], top_n: int) -> list[ScoredChunk]:
        """重排候选块，返回按新分数降序的 ``ScoredChunk`` 列表。"""
        q_tokens = set(lexical_tokens(query))
        scored: list[tuple[int, Chunk, float]] = []
        for index, ch in enumerate(chunks):
            c_tokens = set(lexical_tokens(ch.text))
            union = q_tokens | c_tokens
            overlap = len(q_tokens & c_tokens)
            score = overlap / len(union) if union else 0.0
            scored.append((index, ch, score))
        scored.sort(key=lambda item: item[2], reverse=True)
        return [
            ScoredChunk(chunk=ch, score=score, stage="reranked", rank_before=index + 1, rank_after=after)
            for after, (index, ch, score) in enumerate(scored[:top_n], start=1)
        ]

    def diagnostics(self) -> dict[str, Any]:
        """后端自检；``_error`` 为 ``None`` 表示可用。"""
        return {"backend": self._name, "_error": None}
