# 作者：晨星
"""BM25 词法索引：自写 Robertson IDF，支持中文 bigram（ARCH §7 / T06）。

小语料下 IDF 可为负，属正常（仅改变排名方向，不影响排序单调性，F-? 已知行为）。
"""

from __future__ import annotations

import json
import math

from pathlib import Path

from ..core.text import lexical_tokens
from ..core.types import Chunk, Hit


_K1 = 1.5
_B = 0.75


class Bm25Index:
    """BM25 词法索引；满足 LexicalIndex Protocol。"""

    def __init__(self) -> None:
        self._doc_count = 0
        self._doc_len: dict[str, int] = {}
        self._avg_len = 0.0
        self._tf: dict[str, dict[str, int]] = {}
        self._df: dict[str, int] = {}

    def build(self, chunks: list[Chunk]) -> None:
        """用语料重建索引（替换而非追加）。"""
        self._tf.clear()
        self._df.clear()
        self._doc_len.clear()
        total = 0
        for ch in chunks:
            toks = lexical_tokens(ch.text)
            tf: dict[str, int] = {}
            for tok in toks:
                tf[tok] = tf.get(tok, 0) + 1
            self._tf[ch.chunk_id] = tf
            self._doc_len[ch.chunk_id] = len(toks)
            total += len(toks)
            for tok in tf:
                self._df[tok] = self._df.get(tok, 0) + 1
        self._doc_count = len(chunks)
        self._avg_len = (total / self._doc_count) if self._doc_count else 0.0

    def search(self, query: str, top_k: int) -> list[Hit]:
        """BM25 词法检索，返回 top_k 条命中（source=sparse）。"""
        q_tokens = lexical_tokens(query)
        if not q_tokens or self._doc_count == 0:
            return []
        scores: dict[str, float] = {}
        for tok in set(q_tokens):
            if tok not in self._df:
                continue
            n_t = self._df[tok]
            idf = math.log((self._doc_count - n_t + 0.5) / (n_t + 0.5) + 1.0)
            for cid, tf in self._tf.items():
                if tok not in tf:
                    continue
                dl = self._doc_len[cid]
                denom = tf[tok] * (1.0 - _B + _B * (dl / self._avg_len)) if self._avg_len else tf[tok]
                scores[cid] = scores.get(cid, 0.0) + idf * (tf[tok] * (_K1 + 1.0)) / (tf[tok] + _K1 * denom)
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
        return [
            Hit(chunk_id=cid, score=float(s), source="sparse", rank=r, sparse_rank=r)
            for r, (cid, s) in enumerate(ranked, start=1)
        ]

    def drop_document(self, doc_id: str) -> int:
        """删除某文档全部条目，返回删除条数。"""
        prefix = f"{doc_id}#"
        removed = 0
        for cid in list(self._tf.keys()):
            if cid.startswith(prefix):
                del self._tf[cid]
                del self._doc_len[cid]
                removed += 1
        if removed:
            self._doc_count = max(0, self._doc_count - removed)
        return removed

    def persist(self, path: str) -> None:
        """把索引状态落盘（JSON）。"""
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        state = {"doc_count": self._doc_count, "avg_len": self._avg_len, "tf": self._tf, "df": self._df, "doc_len": self._doc_len}
        (p / "bm25.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    def load(self, path: str) -> None:
        """从目录重载索引。"""
        state = json.loads((Path(path) / "bm25.json").read_text(encoding="utf-8"))
        self._doc_count = state["doc_count"]
        self._avg_len = state["avg_len"]
        self._tf = {k: dict(v) for k, v in state["tf"].items()}
        self._df = dict(state["df"])
        self._doc_len = dict(state["doc_len"])

    def diagnostics(self) -> dict[str, object]:
        """后端自检；``_error`` 为 ``None`` 表示可用。"""
        return {"backend": "bm25", "doc_count": self._doc_count, "_error": None}
