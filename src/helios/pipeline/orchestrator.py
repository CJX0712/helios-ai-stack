# 作者：晨星
"""Pipeline：ingest -> chunk -> embed -> vector/lexical -> fuse -> rerank -> llm -> cite（ARCH §7 / T10）。

所有能力经 registry 按 profile 注入；offline 档零下载零 Key 即可跑通端到端 demo。
"""

from __future__ import annotations

import time

from ..chunk.service import ChunkService
from ..cite.citer import build_citations
from ..core.hashing import stable_key
from ..core.registry import (
    build_embedder,
    build_lexical,
    build_llm,
    build_reranker,
    build_vector,
)
from ..core.types import Answer, Chunk, Document
from ..fuse import reciprocal_rank_fusion
from ..ingest.service import IngestService
from ..llm.template import build_prompt


_CANDIDATE_MULTIPLIER = 4


class Pipeline:
    """端到端 RAG 编排器。"""

    def __init__(self, config) -> None:
        self.config = config
        self.embedder = build_embedder(config)
        self.vector = build_vector(config)
        self.lexical = build_lexical(config)
        self.reranker = build_reranker(config)
        self.llm = build_llm(config)
        self.chunker = ChunkService(config)
        self.ingest = IngestService()
        self._chunks: dict[str, Chunk] = {}
        self._docs: dict[str, Document] = {}

    def add_document(self, text: str, source: str = "") -> Document | None:
        """摄入并索引一篇文档；重复内容返回 ``None``。"""
        doc = self.ingest.ingest(text, source)
        if doc is None:
            return None
        self._docs[doc.doc_id] = doc
        chunks = self.chunker.chunk_document(doc)
        self._chunks.update({c.chunk_id: c for c in chunks})
        vectors = self.embedder.embed([c.text for c in chunks])
        self.vector.add(vectors, [c.chunk_id for c in chunks])
        self.lexical.build(list(self._chunks.values()))
        return doc

    def add_documents(self, items: list[tuple[str, str]]) -> int:
        """批量摄入；返回成功摄入的文档数。"""
        count = 0
        for text, source in items:
            if self.add_document(text, source) is not None:
                count += 1
        return count

    def query(self, question: str, top_k: int | None = None) -> Answer:
        """执行一次完整检索增强问答。"""
        start = time.perf_counter()
        top_k = top_k or self.config.top_k
        candidate_k = top_k * _CANDIDATE_MULTIPLIER

        qvec = self.embedder.embed([question])[0]
        dense = self.vector.search(qvec, candidate_k)
        sparse = self.lexical.search(question, candidate_k)
        fused = reciprocal_rank_fusion(dense, sparse)[:candidate_k]

        fused_chunks = [self._chunks[h.chunk_id] for h in fused if h.chunk_id in self._chunks]
        reranked = self.reranker.rerank(question, fused_chunks, self.config.rerank_top_n)
        top = reranked[:top_k]
        context_chunks = [sc.chunk for sc in top]
        scores = {sc.chunk.chunk_id: sc.score for sc in top}

        prompt = build_prompt(question, context_chunks)
        answer_text = self.llm.generate(prompt)
        citations = build_citations(answer_text, context_chunks, scores=scores, top_n=top_k)

        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return Answer(
            query=question,
            text=answer_text,
            citations=citations,
            timings={"total_ms": round(elapsed_ms, 2)},
            trace_id=stable_key("answer", question, self.config.profile),
            profile=self.config.profile,
            diagnostics={
                "dense_hits": len(dense),
                "sparse_hits": len(sparse),
                "fused": len(fused),
                "reranked": len(top),
                "embedder": self.embedder.diagnostics(),
                "reranker": self.reranker.diagnostics(),
                "llm": self.llm.diagnostics(),
            },
        )

    def get_chunk(self, chunk_id: str) -> Chunk | None:
        """按 chunk_id 取回已索引的块（评测层用）。"""
        return self._chunks.get(chunk_id)

    def doc_sources(self) -> dict[str, str]:
        """返回 ``source -> doc_id`` 映射（评测黄金集按 source 对齐）。"""
        return {doc.source: doc.doc_id for doc in self._docs.values()}

    def retrieve(self, question: str, top_k: int | None = None, rerank: bool = True, mode: str = "hybrid") -> list:
        """返回有序候选 ``ScoredChunk``。

        mode:
            * ``hybrid``：稠密 + 稀疏融合（默认），``rerank=False`` 即为 B0 无重排基线；
            * ``dense``：仅稠密通路；
            * ``sparse``：仅词法通路。
        """
        from ..core.types import ScoredChunk

        top_k = top_k or self.config.top_k
        candidate_k = top_k * _CANDIDATE_MULTIPLIER
        qvec = self.embedder.embed([question])[0]
        dense = self.vector.search(qvec, candidate_k)
        sparse = self.lexical.search(question, candidate_k)

        if mode == "dense":
            ordered = dense[:candidate_k]
        elif mode == "sparse":
            ordered = sparse[:candidate_k]
        else:
            ordered = reciprocal_rank_fusion(dense, sparse)[:candidate_k]

        ordered_chunks = [self._chunks[h.chunk_id] for h in ordered if h.chunk_id in self._chunks]
        if rerank:
            return self.reranker.rerank(question, ordered_chunks, self.config.rerank_top_n)[:top_k]
        return [
            ScoredChunk(chunk=ch, score=0.0, stage="fused", rank_before=i + 1, rank_after=i + 1)
            for i, ch in enumerate(ordered_chunks[:top_k])
        ]

    def persist(self, base_dir: str) -> None:
        """持久化向量与词法索引到 ``base_dir``。"""
        from pathlib import Path

        root = Path(base_dir)
        self.vector.persist(str(root / "vector"))
        if hasattr(self.lexical, "persist"):
            self.lexical.persist(str(root / "lexical"))

    @property
    def document_count(self) -> int:
        """已摄入文档数。"""
        return len(self._docs)

    @property
    def chunk_count(self) -> int:
        """已索引 chunk 数。"""
        return len(self._chunks)
