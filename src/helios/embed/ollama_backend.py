# 作者：晨星
"""Ollama 嵌入后端：调用本机 /api/embed（local 档默认，零下载，ARCH §7 / T04）。"""

from __future__ import annotations

from typing import Any

import numpy as np

from ..core import codes
from ..core.errors import raise_for
from ..core.hashing import l2_normalize
from ..core.net import build_client, ollama_host


class OllamaEmbedder:
    """Ollama 文本嵌入器；满足 Embedder Protocol。"""

    def __init__(self, config: Any | None = None) -> None:
        self.model: str = getattr(config, "embed_model", None) or "bge-m3"
        self.dim: int = int(getattr(config, "embed_dim", None) or 1024)
        self._host = ollama_host()

    def embed(self, texts: list[str]) -> np.ndarray:
        """调用 Ollama 嵌入接口，返回 L2 归一化矩阵。"""
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        import httpx

        try:
            with build_client(base_url=self._host, timeout_s=30.0) as client:
                resp = client.post("/api/embed", json={"model": self.model, "input": list(texts)})
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise raise_for(
                codes.E_EMBED_MODEL_MISSING,
                message="Ollama 嵌入不可用",
                detail={"model": self.model, "error": str(exc)},
            ) from exc

        embeddings = data.get("embeddings") or []
        if not embeddings:
            raise raise_for(codes.E_EMBED_MODEL_MISSING, message="Ollama 返回空嵌入", detail={"model": self.model})
        matrix = np.asarray(embeddings, dtype=np.float64)
        normed = np.vstack([l2_normalize(row) for row in matrix]).astype(np.float32)
        self.dim = int(normed.shape[1])
        return normed

    def diagnostics(self) -> dict[str, Any]:
        """探测 Ollama 就绪与模型存在性。"""
        import httpx

        try:
            with build_client(base_url=self._host, timeout_s=5.0) as client:
                resp = client.get("/api/tags")
                ok = resp.status_code == 200
                models = [m.get("name", "") for m in resp.json().get("models", [])] if ok else []
        except httpx.HTTPError as exc:
            return {"backend": "ollama", "model": self.model, "dim": self.dim, "_error": str(exc), "available_models": []}
        err = None if ok else "ollama 未就绪"
        if ok and self.model not in models:
            err = f"模型 {self.model} 未安装"
        return {"backend": "ollama", "model": self.model, "dim": self.dim, "_error": err, "available_models": models}
