# 作者：晨星
"""兼容层（T16 / P1）：用业界开源成果（LlamaIndex）实现 helios 能力 Protocol。

证明「业务代码（pipeline）零改动即可切换后端」（ARCH §6 / F-21）。
仅当已安装 ``llama-index-core`` 时可用；缺失则 diagnostics 标记 ``_error``，测试 skip 不 fail。
"""

from .llamaindex_adapter import (
    LlamaIndexEmbedder,
    LlamaIndexLLM,
    LlamaIndexReranker,
)


__all__ = ["LlamaIndexEmbedder", "LlamaIndexLLM", "LlamaIndexReranker"]
