# 作者：晨星
"""Faiss 稠密向量索引：IndexFlatIP 余弦检索 + 持久化（local 档默认，ARCH §7 / T05）。"""

from __future__ import annotations

import json

from pathlib import Path

import numpy as np

from ..core import codes
from ..core.errors import raise_for
from ..core.types import Hit


class FaissVectorIndex:
    """Faiss 精确内积索引；向量 L2 归一后内积即余弦。"""

    def __init__(self) -> None:
        self._ids: list[str] = []
        self._matrix: np.ndarray = np.zeros((0, 1), dtype=np.float32)
        self._index = None
        self._dim: int | None = None

    def _build(self) -> None:
        import faiss

        if self._matrix.shape[0] == 0:
            self._index = None
            return
        dim = int(self._matrix.shape[1])
        index = faiss.IndexFlatIP(dim)
        index.add(self._matrix)
        self._index = index

    def add(self, vectors: np.ndarray, ids: list[str]) -> None:
        """写入向量与 id；id 重复按 upsert 语义覆盖。"""
        if len(vectors) != len(ids):
            raise raise_for(codes.E_VECTOR_BAD_INPUT, message="向量与 id 数量不一致")
        vecs = np.asarray(vectors, dtype=np.float32)
        if vecs.ndim != 2:
            raise raise_for(codes.E_VECTOR_BAD_INPUT, message="向量必须是二维")
        if self._dim is None:
            self._dim = int(vecs.shape[1])
        elif vecs.shape[1] != self._dim:
            raise raise_for(codes.E_VECTOR_DIM_MISMATCH, message="维度与已有索引不符")
        for vid in ids:
            self._remove_id(vid)
        self._ids.extend(ids)
        self._matrix = vecs if self._matrix.shape[0] == 0 else np.vstack([self._matrix, vecs])
        self._index = None

    def _remove_id(self, vid: str) -> None:
        drop = [i for i, x in enumerate(self._ids) if x == vid]
        if not drop:
            return
        keep = [i for i in range(self._matrix.shape[0]) if i not in set(drop)]
        self._matrix = self._matrix[keep]
        self._ids = [x for i, x in enumerate(self._ids) if i not in set(drop)]

    def search(self, query: np.ndarray, top_k: int) -> list[Hit]:
        """返回与查询最相似的 top_k 条命中（source=dense）。"""
        if self._index is None:
            self._build()
        if self._index is None or self._index.ntotal == 0:
            return []
        q = np.asarray(query, dtype=np.float32).reshape(1, -1)
        if q.shape[1] != self._dim:
            raise raise_for(codes.E_VECTOR_DIM_MISMATCH, message="查询维度与索引不符")
        scores, indices = self._index.search(q, min(top_k, self._index.ntotal))
        hits: list[Hit] = []
        for rank, (score, idx) in enumerate(zip(scores[0], indices[0], strict=True), start=1):
            if idx < 0:
                continue
            hits.append(
                Hit(chunk_id=self._ids[int(idx)], score=float(score), source="dense", rank=rank, dense_rank=rank)
            )
        return hits

    def drop_document(self, doc_id: str) -> int:
        """删除某文档全部向量，返回删除条数。"""
        prefix = f"{doc_id}#"
        before = len(self._ids)
        mask = [not cid.startswith(prefix) for cid in self._ids]
        keep = [i for i, m in enumerate(mask) if m]
        removed = before - len(keep)
        if removed:
            self._matrix = self._matrix[keep]
            self._ids = [self._ids[i] for i in keep]
            self._index = None
        return removed

    def persist(self, path: str) -> None:
        """落盘索引（faiss 索引 + ids.json）。"""
        import faiss

        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        if self._index is None:
            self._build()
        if self._index is not None:
            faiss.write_index(self._index, str(p / "index.faiss"))
        (p / "ids.json").write_text(json.dumps(self._ids, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: str) -> FaissVectorIndex:
        """从目录重载索引。"""
        import faiss

        p = Path(path)
        index = cls()
        index._index = faiss.read_index(str(p / "index.faiss"))
        index._ids = json.loads((p / "ids.json").read_text(encoding="utf-8"))
        index._dim = index._index.d
        return index
