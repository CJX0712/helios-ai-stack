# 作者：晨星
"""T16 兼容性测试：LlamaIndex adapter 满足 3 个能力 Protocol。

缺 ``llama-index-core`` 时整体 skip（不进 P0 门禁，ARCH F-21）。
"""
from __future__ import annotations

import importlib.util

import pytest

from ...core.protocols import LLM, Embedder, Reranker
from ..llamaindex_adapter import LlamaIndexEmbedder, LlamaIndexLLM, LlamaIndexReranker


pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("llama_index") is None,
    reason="llama-index-core 未安装，T16 兼容性证明跳过（不进 P0 门禁）",
)


def test_protocol_conformance() -> None:
    assert isinstance(LlamaIndexEmbedder(), Embedder)
    assert isinstance(LlamaIndexLLM(), LLM)
    assert isinstance(LlamaIndexReranker(), Reranker)


def test_diagnostics_available() -> None:
    assert LlamaIndexEmbedder().diagnostics()["_error"] is None
    assert LlamaIndexLLM().diagnostics()["_error"] is None
    assert LlamaIndexReranker().diagnostics()["_error"] is None
