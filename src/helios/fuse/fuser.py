# 作者：晨星
"""Reciprocal Rank Fusion：鲁棒合并稠密与稀疏两通路（ARCH §7 / T07）。

RRF 仅依赖位次、对分数量纲不敏感，因此稠密 cosine 与 BM25 可直接相加而不必归一。
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from ..core.types import Hit


_RRF_K = 60


def reciprocal_rank_fusion(
    dense: list[Hit], sparse: list[Hit], k: int = _RRF_K, top_k: int | None = None
) -> list[Hit]:
    """合并两通路命中，返回按融合分降序的 ``Hit`` 列表（source=fused）。"""
    accum: dict[str, dict[str, Any]] = defaultdict(lambda: {"score": 0.0})
    for hit in dense:
        e = accum[hit.chunk_id]
        e["score"] += 1.0 / (k + hit.rank)
        e["dense_rank"] = hit.rank
    for hit in sparse:
        e = accum[hit.chunk_id]
        e["score"] += 1.0 / (k + hit.rank)
        e["sparse_rank"] = hit.rank
    ordered = sorted(accum.items(), key=lambda kv: kv[1]["score"], reverse=True)
    if top_k is not None:
        ordered = ordered[:top_k]
    fused: list[Hit] = []
    for rank, (cid, info) in enumerate(ordered, start=1):
        fused.append(
            Hit(
                chunk_id=cid,
                score=float(info["score"]),
                source="fused",
                rank=rank,
                dense_rank=info.get("dense_rank"),
                sparse_rank=info.get("sparse_rank"),
                fused_score=float(info["score"]),
            )
        )
    return fused


class Fuser:
    """融合器可注入封装（RRF 默认实现）。"""

    def __init__(self, config: Any | None = None) -> None:
        self._k = int(getattr(config, "candidate_multiplier", None) or _RRF_K)

    def fuse(self, dense: list[Hit], sparse: list[Hit], top_k: int | None = None) -> list[Hit]:
        """融合稠密与稀疏命中。"""
        return reciprocal_rank_fusion(dense, sparse, k=self._k, top_k=top_k)
