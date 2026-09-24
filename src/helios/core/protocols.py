# 作者：晨星
"""五个能力 Protocol：上层模块之间只经 dataclass 与 Protocol 通信（ARCH C4 / C5 / §8.2）。

约定：
    * 全部外部依赖 = 「Protocol + 可注入实现」，**默认实现必须是真实现，不是 stub**（C5）；
    * ``diagnostics()`` 必须返回含 ``"_error"`` 键的字典，评测侧据此断言后端未静默回退（F-2b）；
    * ``core`` 层不 import 任何上层模块，只声明契约。
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Protocol, runtime_checkable

import numpy as np

from .types import Chunk, Hit, ScoredChunk


@runtime_checkable
class Embedder(Protocol):
    """文本 -> 稠密向量。"""

    #: 输出维度；实际输出维度不符时抛 ``E_EMBED_DIM_MISMATCH``。
    dim: int

    def embed(self, texts: list[str]) -> np.ndarray:
        """把文本列表编码成 ``[N, D]`` 的 float32 矩阵，行向量 L2 归一。"""
        ...

    def diagnostics(self) -> dict[str, Any]:
        """返回后端自检信息，必须含 ``"_error": str | None``。"""
        ...


@runtime_checkable
class VectorIndex(Protocol):
    """稠密索引的增删查与持久化。"""

    def add(self, vectors: np.ndarray, ids: list[str]) -> None:
        """写入向量与对应 id；id 重复时按 upsert 语义覆盖。"""
        ...

    def search(self, query: np.ndarray, top_k: int) -> list[Hit]:
        """检索与查询向量最相近的 top_k 条命中。"""
        ...

    def drop_document(self, doc_id: str) -> int:
        """删除某文档的全部向量，返回删除条数（F-9 防孤儿）。"""
        ...

    def persist(self, path: str) -> None:
        """把索引落盘到目录 path。"""
        ...

    @classmethod
    def load(cls, path: str) -> VectorIndex:
        """从目录 path 重载索引。"""
        ...


@runtime_checkable
class LexicalIndex(Protocol):
    """稀疏 / 词法索引。"""

    def build(self, chunks: list[Chunk]) -> None:
        """用语料重建索引（替换而非追加）。"""
        ...

    def search(self, query: str, top_k: int) -> list[Hit]:
        """词法检索，返回 top_k 条命中。"""
        ...

    def drop_document(self, doc_id: str) -> int:
        """删除某文档的全部条目，返回删除条数。"""
        ...

    def persist(self, path: str) -> None:
        """把索引状态落盘到目录 path。"""
        ...


@runtime_checkable
class Reranker(Protocol):
    """对 top-N 候选做重排。"""

    def rerank(self, query: str, chunks: list[Chunk], top_n: int) -> list[ScoredChunk]:
        """重排候选块，返回按新分数降序的 ``ScoredChunk`` 列表。"""
        ...


@runtime_checkable
class LLM(Protocol):
    """生成与流式生成。"""

    def generate(self, prompt: str) -> str:
        """一次性生成完整回答。"""
        ...

    def stream(self, prompt: str) -> Iterator[str]:
        """流式生成，逐段产出文本。"""
        ...


#: 五项能力的注册名，供 registry 与分层守护测试共用。
CAPABILITIES: tuple[str, ...] = ("embed", "vector", "lexical", "rerank", "llm")
