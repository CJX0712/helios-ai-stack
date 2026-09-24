# 作者：晨星
"""倒排索引：token -> chunk 列表，TF-IDF 打分（词法后端备选，ARCH §7 / T06）。"""

from __future__ import annotations

import json

from pathlib import Path

from ..core.text import lexical_tokens
from ..core.types import Chunk, Hit


class InvertedIndex:
    """简单 TF-IDF 倒排索引；满足 LexicalIndex Protocol。"""

    def __init__(self) -> None:
        self._postings: dict[str, list[str]] = {}
        self._tf: dict[str, dict[str, int]] = {}
        self._doc_count = 0

    def build(self, chunks: list[Chunk]) -> None:
        """用语料重建索引。"""
        self._postings.clear()
        self._tf.clear()
        for ch in chunks:
            toks = lexical_tokens(ch.text)
            tf: dict[str, int] = {}
            for tok in toks:
                tf[tok] = tf.get(tok, 0) + 1
                self._postings.setdefault(tok, []).append(ch.chunk_id)
            self._tf[ch.chunk_id] = tf
        self._doc_count = len(chunks)

    def search(self, query: str, top_k: int) -> list[Hit]:
        """TF-IDF 检索，返回 top_k 条命中（source=sparse）。"""
        q_tokens = lexical_tokens(query)
        if not q_tokens or self._doc_count == 0:
            return []
        scores: dict[str, float] = {}
        for tok in set(q_tokens):
            if tok not in self._postings:
                continue
            idf = math_log_idf(self._doc_count, len(self._postings[tok]))
            for cid in self._postings[tok]:
                scores[cid] = scores.get(cid, 0.0) + idf * (1.0 + math_log_tf(self._tf[cid][tok]))
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
        return [
            Hit(chunk_id=cid, score=float(s), source="sparse", rank=r, sparse_rank=r)
            for r, (cid, s) in enumerate(ranked, start=1)
        ]

    def drop_document(self, doc_id: str) -> int:
        """删除某文档全部条目，返回删除条数。"""
        prefix = f"{doc_id}#"
        removed = 0
        for tok in list(self._postings.keys()):
            before = len(self._postings[tok])
            self._postings[tok] = [c for c in self._postings[tok] if not c.startswith(prefix)]
            if len(self._postings[tok]) != before:
                removed += 1
        for cid in list(self._tf.keys()):
            if cid.startswith(prefix):
                del self._tf[cid]
        if removed:
            self._doc_count = max(0, self._doc_count - removed)
        return removed

    def persist(self, path: str) -> None:
        """落盘索引状态（JSON）。"""
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        state = {"doc_count": self._doc_count, "postings": self._postings, "tf": self._tf}
        (p / "inverted.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    def load(self, path: str) -> None:
        """重载索引状态。"""
        state = json.loads((Path(path) / "inverted.json").read_text(encoding="utf-8"))
        self._doc_count = state["doc_count"]
        self._postings = {k: list(v) for k, v in state["postings"].items()}
        self._tf = {k: dict(v) for k, v in state["tf"].items()}

    def diagnostics(self) -> dict[str, object]:
        """后端自检；``_error`` 为 ``None`` 表示可用。"""
        return {"backend": "inverted", "doc_count": self._doc_count, "_error": None}


def math_log_idf(doc_count: int, df: int) -> float:
    """平滑 IDF，避免除零与负无穷。"""
    import math

    return math.log((doc_count + 1.0) / (df + 1.0)) + 1.0


def math_log_tf(tf: int) -> float:
    """sublinear TF 变换。"""
    import math

    return math.log1p(float(tf))
