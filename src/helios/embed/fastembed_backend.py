# 作者：晨星
"""FastEmbed 嵌入后端（可选增强；不可达则回落 hashing，ARCH §7 / T04）。"""

from __future__ import annotations

from typing import Any

import numpy as np

from ..core import codes
from ..core.errors import raise_for


class FastembedBackend:
    """封装 fastembed.TextEmbedding；满足 Embedder Protocol。"""

    def __init__(self, config: Any | None = None) -> None:
        self.model: str = getattr(config, "embed_model", None) or "BAAI/bge-small-en-v1.5"
        self.dim: int = int(getattr(config, "embed_dim", None) or 384)
        self._engine = None

    def _ensure(self):
        try:
            from fastembed import TextEmbedding
        except ImportError as exc:  # pragma: no cover - 可选依赖缺失
            raise raise_for(codes.E_EMBED_MODEL_MISSING, message="fastembed 不可用", detail={"error": str(exc)}) from exc
        if self._engine is None:
            self._engine = TextEmbedding(model_name=self.model)
        return self._engine

    def embed(self, texts: list[str]) -> np.ndarray:
        """批量嵌入；fastembed 默认输出 L2 归一向量。"""
        engine = self._ensure()
        out = list(engine.embed(list(texts)))
        return np.asarray(out, dtype=np.float32)

    def diagnostics(self) -> dict[str, Any]:
        """后端自检；``_error`` 为 ``None`` 表示可用。"""
        try:
            self._ensure()
        except Exception as exc:  # pragma: no cover - 依赖/网络缺失分支
            return {"backend": "fastembed", "model": self.model, "dim": self.dim, "_error": str(exc)}
        return {"backend": "fastembed", "model": self.model, "dim": self.dim, "_error": None}
