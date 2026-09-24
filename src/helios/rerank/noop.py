# 作者：晨星
"""无重排基线（B0）：保持融合顺序，供对照实验（ARCH §7 / T08）。"""

from __future__ import annotations

from typing import Any

from ..core.types import Chunk, ScoredChunk


class NoopReranker:
    """不做重排，原样返回；满足 Reranker Protocol。"""

    def __init__(self, config: Any | None = None) -> None:
        self._name = "none"

    def rerank(self, query: str, chunks: list[Chunk], top_n: int) -> list[ScoredChunk]:
        """保持输入顺序，仅截断到 ``top_n``。"""
        return [
            ScoredChunk(chunk=ch, score=0.0, stage="reranked", rank_before=i + 1, rank_after=i + 1)
            for i, ch in enumerate(chunks[:top_n])
        ]

    def diagnostics(self) -> dict[str, Any]:
        """后端自检；``_error`` 为 ``None`` 表示可用。"""
        return {"backend": self._name, "_error": None}
