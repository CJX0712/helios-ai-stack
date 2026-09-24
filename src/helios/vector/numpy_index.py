# 作者：晨星
"""Numpy 稠密向量索引：cosine 检索 + 持久化（offline 默认后端，ARCH §7）。"""

from __future__ import annotations

import json

from pathlib import Path

import numpy as np

from ..core import codes
from ..core.errors import raise_for
from ..core.types import Hit


class NumpyVectorIndex:
    """纯 numpy 稠密索引；向量 L2 归一后 cosine = 点积。"""

    def __init__(self) -> None:
        self._ids: list[str] = []
        self._matrix: np.ndarray = np.zeros((0, 1), dtype=np.float32)
        self._dim: int | None = None

    def add(self, vectors: np.ndarray, ids: list[str]) -> None:
        """写入向量与 id；id 重复按 upsert 语义覆盖。"""
        if len(vectors) != len(ids):
            raise raise_for(
                codes.E_VECTOR_BAD_INPUT,
                message="向量与 id 数量不一致",
                detail={"vectors": int(len(vectors)), "ids": len(ids)},
            )
        vecs = np.asarray(vectors, dtype=np.float32)
        if vecs.ndim != 2:
            raise raise_for(codes.E_VECTOR_BAD_INPUT, message="向量必须是二维")
        if self._dim is None:
            self._dim = int(vecs.shape[1])
        elif vecs.shape[1] != self._dim:
            raise raise_for(
                codes.E_VECTOR_DIM_MISMATCH,
                message="维度与已有索引不符",
                detail={"expected": self._dim, "got": int(vecs.shape[1])},
            )
        for vid in ids:
            self._remove_id(vid)
        self._ids.extend(ids)
        self._matrix = vecs if self._matrix.shape[0] == 0 else np.vstack([self._matrix, vecs])

    def _remove_id(self, vid: str) -> None:
        idx = [i for i, x in enumerate(self._ids) if x == vid]
        if not idx:
            return
        drop = set(idx)
        keep = [i for i in range(self._matrix.shape[0]) if i not in drop]
        self._matrix = self._matrix[keep]
        self._ids = [x for i, x in enumerate(self._ids) if i not in drop]

    def search(self, query: np.ndarray, top_k: int) -> list[Hit]:
        """返回与查询最相似的 top_k 条命中（source=dense）。"""
        q = np.asarray(query, dtype=np.float32).reshape(-1)
        if self._matrix.shape[0] == 0:
            return []
        if q.shape[0] != self._matrix.shape[1]:
            raise raise_for(
                codes.E_VECTOR_DIM_MISMATCH,
                message="查询维度与索引不符",
                detail={"index_dim": int(self._matrix.shape[1]), "query_dim": int(q.shape[0])},
            )
        sims = self._matrix @ q
        k = min(top_k, len(self._ids))
        order = np.argsort(-sims)[:k]
        hits: list[Hit] = []
        for rank, i in enumerate(order, start=1):
            hits.append(
                Hit(chunk_id=self._ids[int(i)], score=float(sims[i]), source="dense", rank=rank, dense_rank=rank)
            )
        return hits

    def drop_document(self, doc_id: str) -> int:
        """删除某文档全部向量，返回删除条数（防孤儿）。"""
        prefix = f"{doc_id}#"
        mask = np.array([cid.startswith(prefix) for cid in self._ids])
        removed = int(mask.sum())
        if removed:
            self._matrix = self._matrix[~mask]
            self._ids = [cid for cid, m in zip(self._ids, mask, strict=True) if not m]
        return removed

    def persist(self, path: str) -> None:
        """把索引落盘到目录（vectors.npy + ids.json）。"""
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        np.save(str(p / "vectors.npy"), self._matrix)
        (p / "ids.json").write_text(json.dumps(self._ids, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> NumpyVectorIndex:
        """从目录重载索引。"""
        p = Path(path)
        index = cls()
        matrix = np.load(str(p / "vectors.npy"))
        ids = json.loads((p / "ids.json").read_text(encoding="utf-8"))
        index._matrix = matrix
        index._ids = ids
        index._dim = int(matrix.shape[1]) if matrix.shape[0] else 1
        return index

    def diagnostics(self) -> dict[str, object]:
        """后端自检；``_error`` 为 ``None`` 表示可用。"""
        return {"backend": "numpy", "count": len(self._ids), "dim": self._dim, "_error": None}
