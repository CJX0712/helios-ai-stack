# 作者：晨星
"""远端重排（OpenAI 兼容 / Cohere 风格）；网络闸门关闭则抛错回落（ARCH §7 / T08）。"""

from __future__ import annotations

from typing import Any

from ..core import codes
from ..core.errors import raise_for
from ..core.net import build_client, guard
from ..core.types import Chunk, ScoredChunk


class RemoteReranker:
    """调用远端重排端点；满足 Reranker Protocol。"""

    def __init__(self, config: Any | None = None) -> None:
        self._endpoint: str = getattr(config, "rerank_model", None) or os_environ("HELIOS_RERANK_URL", "")
        self._api_key: str = os_environ("HELIOS_RERANK_API_KEY", "")

    def rerank(self, query: str, chunks: list[Chunk], top_n: int) -> list[ScoredChunk]:
        """请求远端重排并映射为 ScoredChunk。"""
        if not self._endpoint:
            raise raise_for(codes.E_RERANK_MODEL_MISSING, message="未配置远端重排端点（HELIOS_RERANK_URL）")
        guard(self._endpoint, component="rerank")
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        payload = {"query": query, "documents": [c.text for c in chunks], "top_n": top_n}
        with build_client(timeout_s=30.0) as client:
            resp = client.post(self._endpoint, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        ranked = data.get("results", [])
        if not ranked:
            ranked = [
                {"index": i, "relevance_score": 0.0} for i in range(len(chunks))
            ]
        scores_by_index: dict[int, float] = {int(r["index"]): float(r.get("relevance_score", 0.0)) for r in ranked}
        order = sorted(range(len(chunks)), key=lambda i: scores_by_index.get(i, 0.0), reverse=True)[:top_n]
        return [
            ScoredChunk(chunk=chunks[i], score=scores_by_index.get(i, 0.0), stage="reranked", rank_before=i + 1, rank_after=after)
            for after, i in enumerate(order, start=1)
        ]

    def diagnostics(self) -> dict[str, Any]:
        """后端自检；``_error`` 为 ``None`` 表示可用。"""
        if not self._endpoint:
            return {"backend": "remote", "_error": "未配置 HELIOS_RERANK_URL"}
        return {"backend": "remote", "endpoint": self._endpoint, "_error": None}


def os_environ(key: str, default: str) -> str:
    """读取环境变量，缺省回退 default。"""
    import os

    return os.environ.get(key, default)
