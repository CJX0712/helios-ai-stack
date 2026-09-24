# 作者：晨星
"""ONNX 交叉编码器重排（可选增强；缺模型则回落 lexical，ARCH §7 / T08）。"""

from __future__ import annotations

import os

from typing import Any

from ..core import codes
from ..core.errors import raise_for
from ..core.types import Chunk, ScoredChunk


class OnnxReranker:
    """本地 ONNX 交叉编码器重排器；满足 Reranker Protocol。"""

    def __init__(self, config: Any | None = None) -> None:
        self.model: str = getattr(config, "rerank_model", None) or "Xenova/ms-marco-MiniLM-L-6-v2"
        self._model_dir: str = os.environ.get("HELIOS_MODEL_DIR", getattr(config, "model_dir", "models/"))
        self._session = None
        self._tokenizer = None

    def _ensure(self) -> None:
        if self._session is not None:
            return
        try:
            import onnxruntime as ort

            from transformers import AutoTokenizer
        except ImportError as exc:  # pragma: no cover - 可选依赖缺失
            raise raise_for(codes.E_RERANK_MODEL_MISSING, message="缺少 transformers/onnxruntime", detail={"error": str(exc)}) from exc
        path = os.path.join(self._model_dir, self.model)
        onnx_path = os.path.join(path, "onnx", "model.onnx")
        if not os.path.isfile(onnx_path):
            onnx_path = os.path.join(path, "model.onnx")
        if not os.path.isfile(onnx_path):
            raise raise_for(codes.E_RERANK_MODEL_MISSING, message="ONNX 重排模型缺失", detail={"path": onnx_path})
        self._tokenizer = AutoTokenizer.from_pretrained(path)
        self._session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])

    def rerank(self, query: str, chunks: list[Chunk], top_n: int) -> list[ScoredChunk]:
        """对 query-chunk 对做交叉编码打分并排序。"""
        self._ensure()
        assert self._tokenizer is not None and self._session is not None
        scores: list[float] = []
        for ch in chunks:
            enc = self._tokenizer(query, ch.text, truncation=True, max_length=512, return_tensors="np")
            out = self._session.run(None, {k: v for k, v in enc.items()})
            logits = out[0]
            score = float(logits.reshape(-1)[0] if logits.ndim >= 1 else 0.0)
            scores.append(score)
        order = sorted(range(len(chunks)), key=lambda i: scores[i], reverse=True)[:top_n]
        return [
            ScoredChunk(chunk=chunks[i], score=scores[i], stage="reranked", rank_before=i + 1, rank_after=after)
            for after, i in enumerate(order, start=1)
        ]

    def diagnostics(self) -> dict[str, Any]:
        """后端自检；``_error`` 为 ``None`` 表示可用。"""
        try:
            self._ensure()
        except Exception as exc:  # pragma: no cover - 依赖/模型缺失分支
            return {"backend": "onnx", "model": self.model, "_error": str(exc)}
        return {"backend": "onnx", "model": self.model, "_error": None}
