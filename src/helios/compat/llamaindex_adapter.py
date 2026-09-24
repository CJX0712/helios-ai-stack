# 作者：晨星
"""LlamaIndex 兼容 adapter（T16 / P1）：以 LlamaIndex 实现 helios 的 3 个能力 Protocol。

实现：``Embedder`` / ``LLM`` / ``Reranker``（满足「至少 3 个」要求）。
全部依赖惰性导入，缺 ``llama-index-core`` 时 ``diagnostics()`` 返回 ``_error`` 标记，
业务侧经 registry 降级链自动跳过，不进 P0 验收链。

用法（需先 ``pip install llama-index-core`` 并配置 ``Settings.embed_model`` / ``Settings.llm``）：

    from helios.compat import LlamaIndexEmbedder
    registry.register("embed", "llamaindex", LlamaIndexEmbedder)  # 业务代码零改动切换
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import numpy as np

from ..core import codes
from ..core.errors import raise_for
from ..core.types import Chunk, ScoredChunk


def _llama_index_or_raise(code: str, message: str) -> Any:
    """惰性导入 llama_index.core；缺失即按对应能力错误码抛出。"""
    try:
        import llama_index.core as lic

        return lic
    except Exception as exc:  # 缺依赖：交给上层降级，不静默吞掉
        raise raise_for(code, message=message, detail={"error": str(exc)}) from exc


class LlamaIndexEmbedder:
    """Embedder 实现：委托 ``llama_index.core.settings.Settings.embed_model``。"""

    def __init__(self, config: Any | None = None) -> None:
        lic = _llama_index_or_raise(codes.E_EMBED_MODEL_MISSING, "LlamaIndex 嵌入后端不可用")
        try:
            self._model = lic.settings.Settings.embed_model
            meta = getattr(self._model, "model_meta", None)
            self.dim = int(getattr(meta, "output_dimension", 384)) if meta else 384
        except Exception as exc:
            raise raise_for(codes.E_EMBED_MODEL_MISSING, message="未配置 embed_model", detail={"error": str(exc)}) from exc

    def embed(self, texts: list[str]) -> np.ndarray:
        """编码为 ``[N, D]`` 的 float32 矩阵，行向量 L2 归一。"""
        vecs = self._model.get_text_embedding_batch(texts)
        arr = np.asarray(vecs, dtype=np.float32)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return arr / norms

    def diagnostics(self) -> dict[str, Any]:
        """后端自检；``_error`` 为 ``None`` 表示可用。"""
        try:
            _llama_index_or_raise(codes.E_EMBED_MODEL_MISSING, "LlamaIndex 嵌入后端不可用")
            return {"backend": "llamaindex.embedder", "_error": None}
        except Exception as exc:
            return {"backend": "llamaindex.embedder", "_error": str(exc)}


class LlamaIndexLLM:
    """LLM 实现：委托 ``llama_index.core.settings.Settings.llm``。"""

    def __init__(self, config: Any | None = None) -> None:
        lic = _llama_index_or_raise(codes.E_LLM_MODEL_MISSING, "LlamaIndex 生成后端不可用")
        try:
            self._llm = lic.settings.Settings.llm
        except Exception as exc:
            raise raise_for(codes.E_LLM_MODEL_MISSING, message="未配置 llm", detail={"error": str(exc)}) from exc

    def generate(self, prompt: str) -> str:
        """一次性生成完整回答。"""
        resp = self._llm.complete(prompt)
        return resp.text if hasattr(resp, "text") else str(resp)

    def stream(self, prompt: str) -> Iterator[str]:
        """流式生成，逐段产出文本。"""
        for piece in self._llm.stream_complete(prompt):
            text = piece.text if hasattr(piece, "text") else str(piece)
            if text:
                yield text

    def diagnostics(self) -> dict[str, Any]:
        """后端自检；``_error`` 为 ``None`` 表示可用。"""
        try:
            _llama_index_or_raise(codes.E_LLM_MODEL_MISSING, "LlamaIndex 生成后端不可用")
            return {"backend": "llamaindex.llm", "_error": None}
        except Exception as exc:
            return {"backend": "llamaindex.llm", "_error": str(exc)}


class LlamaIndexReranker:
    """Reranker 实现：委托 ``llama_index.core.postprocessor.FlagEmbeddingReranker``。"""

    def __init__(self, config: Any | None = None, model: str = "BAAI/bge-reranker-base", top_n: int = 8) -> None:
        lic = _llama_index_or_raise(codes.E_RERANK_MODEL_MISSING, "LlamaIndex 重排后端不可用")
        from llama_index.core.postprocessor import FlagEmbeddingReranker

        self._lic = lic
        self._model = model
        self._top_n = top_n
        self._reranker = FlagEmbeddingReranker(model=model, top_n=top_n)

    def rerank(self, query: str, chunks: list[Chunk], top_n: int) -> list[ScoredChunk]:
        """重排候选块，返回按新分数降序的 ``ScoredChunk`` 列表。"""
        from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode

        nodes = [
            NodeWithScore(node=TextNode(text=c.text, id_=c.chunk_id, metadata={"chunk_id": c.chunk_id}), score=0.0)
            for c in chunks
        ]
        bundle = QueryBundle(query_str=query)
        ranked = self._reranker.postprocess_nodes(nodes, query_bundle=bundle)
        out: list[ScoredChunk] = []
        for i, nws in enumerate(ranked[:top_n], start=1):
            cid = getattr(nws.node, "id_", None) or nws.node.metadata.get("chunk_id")
            chunk = next((c for c in chunks if c.chunk_id == cid), chunks[0])
            out.append(
                ScoredChunk(
                    chunk=chunk,
                    score=float(getattr(nws, "score", 0.0) or 0.0),
                    stage="reranked",
                    rank_before=next((j + 1 for j, c in enumerate(chunks) if c.chunk_id == cid), 1),
                    rank_after=i,
                )
            )
        return out

    def diagnostics(self) -> dict[str, Any]:
        """后端自检；``_error`` 为 ``None`` 表示可用。"""
        try:
            _llama_index_or_raise(codes.E_RERANK_MODEL_MISSING, "LlamaIndex 重排后端不可用")
            return {"backend": "llamaindex.reranker", "model": self._model, "_error": None}
        except Exception as exc:
            return {"backend": "llamaindex.reranker", "model": self._model, "_error": str(exc)}
