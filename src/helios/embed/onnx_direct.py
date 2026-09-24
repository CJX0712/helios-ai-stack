# 作者：晨星
"""ONNX 直接嵌入后端（可选增强；缺模型则回落 hashing，ARCH §7 / T04）。"""

from __future__ import annotations

import os

from typing import Any

import numpy as np

from ..core import codes
from ..core.errors import raise_for
from ..core.hashing import l2_normalize


class OnnxDirectEmbedder:
    """本地 ONNX 嵌入模型（需 transformers + onnxruntime + 本地权重）。"""

    def __init__(self, config: Any | None = None) -> None:
        self.model: str = getattr(config, "embed_model", None) or "bge-m3"
        self.dim: int = int(getattr(config, "embed_dim", None) or 1024)
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
            raise raise_for(
                codes.E_EMBED_MODEL_MISSING, message="缺少 transformers/onnxruntime", detail={"error": str(exc)}
            ) from exc
        path = os.path.join(self._model_dir, self.model)
        onnx_path = os.path.join(path, "model.onnx")
        if not os.path.isfile(onnx_path):
            raise raise_for(codes.E_EMBED_MODEL_MISSING, message="ONNX 模型缺失", detail={"path": onnx_path})
        self._tokenizer = AutoTokenizer.from_pretrained(path)
        self._session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])

    def embed(self, texts: list[str]) -> np.ndarray:
        """加载权重、均值池化、L2 归一化。"""
        self._ensure()
        assert self._tokenizer is not None and self._session is not None
        matrix = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            enc = self._tokenizer(text, truncation=True, max_length=512, return_tensors="np")
            out = self._session.run(None, {k: v for k, v in enc.items()})
            last = out[0][0]
            pooled = l2_normalize(np.mean(last, axis=0))
            matrix[i] = pooled
        return matrix

    def diagnostics(self) -> dict[str, Any]:
        """后端自检；``_error`` 为 ``None`` 表示可用。"""
        try:
            self._ensure()
        except Exception as exc:  # pragma: no cover - 依赖/模型缺失分支
            return {"backend": "onnx", "model": self.model, "dim": self.dim, "_error": str(exc)}
        return {"backend": "onnx", "model": self.model, "dim": self.dim, "_error": None}
