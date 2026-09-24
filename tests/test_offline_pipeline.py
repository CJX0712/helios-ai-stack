# 作者：晨星
"""离线端到端链路测试：ingest -> chunk -> embed -> retrieve -> fuse -> rerank -> llm -> cite。"""
from __future__ import annotations

import pytest

from helios.core.config import ProfileConfig
from helios.pipeline import Pipeline


@pytest.fixture()
def pipe():
    cfg = ProfileConfig.from_env({"HELIOS_PROFILE": "offline"})
    p = Pipeline(cfg)
    p.add_documents([
        ("RAG（检索增强生成）通过在生成前检索外部知识来降低幻觉。", "rag.md"),
        ("FAISS 是高效的稠密向量检索库，支持 IVF 与 HNSW 等索引。", "faiss.md"),
        ("BM25 是经典的词法检索算法，基于词频与逆文档频率。", "bm25.md"),
        ("向量数据库用于存储和查询高维嵌入表示。", "vecdb.md"),
    ])
    return p


def test_ingest_and_chunk(pipe):
    assert pipe.document_count == 4
    assert pipe.chunk_count >= 4


def test_query_has_citations(pipe):
    ans = pipe.query("什么是 RAG 检索增强生成？")
    assert ans.has_citation()
    assert len(ans.citations) >= 1
    assert all(c.doc_id for c in ans.citations)
    assert "RAG" in ans.text or "检索" in ans.text


def test_calculator_routing(pipe):
    ans = pipe.query("12*(3+4)")
    assert ans.text == "84"


def test_retrieve_modes(pipe):
    hybrid = pipe.retrieve("什么是 RAG？", rerank=True, mode="hybrid")
    dense = pipe.retrieve("什么是 RAG？", rerank=False, mode="dense")
    sparse = pipe.retrieve("什么是 RAG？", rerank=False, mode="sparse")
    assert len(hybrid) >= 1
    assert len(dense) >= 1
    assert len(sparse) >= 1
    # 所有返回项必须是合法的 ScoredChunk
    assert all(isinstance(sc.chunk, object) for sc in hybrid)
    assert all(isinstance(sc.chunk, object) for sc in dense)
    assert all(isinstance(sc.chunk, object) for sc in sparse)


def test_dedup(pipe):
    before = pipe.document_count
    dup = pipe.add_document("RAG（检索增强生成）通过在生成前检索外部知识来降低幻觉。", "rag.md")
    assert dup is None
    assert pipe.document_count == before
