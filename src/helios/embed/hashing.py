# 作者：晨星
"""确定性哈希嵌入：零依赖、零下载、offline 默认后端（ARCH §7 / T04）。

用 signed hashing trick 把文本压成定维 L2 归一向量；同输入逐位相等，是「干净环境一键复现」支点。
"""

from __future__ import annotations

from typing import Any

import numpy as np

from ..core.hashing import hash_text_matrix
from ..core.types import Chunk


class HashingEmbedder:
    """确定性哈希嵌入器；满足 Embedder Protocol。"""

    def __init__(self, config: Any | None = None) -> None:
        self.dim: int = int(getattr(config, "embed_dim", None) or 384)

    def embed(self, texts: list[str]) -> np.ndarray:
        """文本列表 -> ``[N, dim]`` float32 矩阵，行向量 L2 归一。"""
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return hash_text_matrix(list(texts), self.dim)

    def embed_chunks(self, chunks: list[Chunk]) -> np.ndarray:
        """便捷方法：直接对 Chunk 列表编码。"""
        return self.embed([c.text for c in chunks])

    def diagnostics(self) -> dict[str, Any]:
        """后端自检；``_error`` 为 ``None`` 表示可用。"""
        return {"backend": "hashing", "dim": self.dim, "_error": None}
