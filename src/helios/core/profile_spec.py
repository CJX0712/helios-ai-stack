# 作者：晨星
"""profile 配置数据表（T02）：从 config.py 析出以控制单文件行数（ARCH §6）。

仅含不可变数据；不 import config / types，避免循环依赖。
config.py 经 ``from .profile_spec import ...`` 重新绑定同名导出，调用方无感。
"""

from __future__ import annotations


#: 各档位的默认后端绑定（换实现只改这一处，ARCH §6）。
PROFILE_BACKENDS: dict[str, dict[str, str]] = {
    "offline": {
        "embed_backend": "hashing",
        "vector_backend": "numpy",
        "lexical_backend": "bm25",
        "rerank_backend": "lexical",
        "llm_backend": "template",
        "allow_network": 0,
    },
    "local": {
        "embed_backend": "ollama",
        "vector_backend": "faiss",
        "lexical_backend": "bm25",
        "rerank_backend": "onnx",
        "llm_backend": "llama_cpp",
        "allow_network": 1,
    },
    "remote": {
        "embed_backend": "ollama",
        "vector_backend": "faiss",
        "lexical_backend": "bm25",
        "rerank_backend": "remote",
        "llm_backend": "openai",
        "allow_network": 1,
    },
}

#: 需要按 int 解析的字段。
INT_FIELDS: frozenset[str] = frozenset(
    {
        "embed_dim",
        "llm_threads",
        "llm_ctx",
        "top_k",
        "rerank_top_n",
        "candidate_multiplier",
        "chunk_size",
        "chunk_overlap",
        "min_chunk_chars",
        "embed_batch_size",
        "timeout_search_ms",
        "timeout_llm_ms",
        "allow_network",
        "strict_backends",
        "enable_calculator",
    }
)

#: 环境变量 -> 字段名的覆盖表（ARCH §6.1）。
ENV_FIELDS: dict[str, str] = {
    "HELIOS_PROFILE": "profile",
    "HELIOS_EMBED_BACKEND": "embed_backend",
    "HELIOS_EMBED_MODEL": "embed_model",
    "HELIOS_EMBED_DIM": "embed_dim",
    "HELIOS_VECTOR_BACKEND": "vector_backend",
    "HELIOS_LEXICAL_BACKEND": "lexical_backend",
    "HELIOS_RERANK_BACKEND": "rerank_backend",
    "HELIOS_RERANK_MODEL": "rerank_model",
    "HELIOS_LLM_BACKEND": "llm_backend",
    "HELIOS_LLM_MODEL": "llm_model",
    "HELIOS_LLM_THREADS": "llm_threads",
    "HELIOS_LLM_CTX": "llm_ctx",
    "HELIOS_MODEL_DIR": "model_dir",
    "HELIOS_DATA_DIR": "data_dir",
    "HELIOS_INDEX_DIR": "index_dir",
    "HELIOS_CACHE_DIR": "cache_dir",
    "HELIOS_OLLAMA_HOST": "ollama_host",
    "HELIOS_LOG_LEVEL": "log_level",
    "HELIOS_TIMEOUT_SEARCH_MS": "timeout_search_ms",
    "HELIOS_TIMEOUT_LLM_MS": "timeout_llm_ms",
    "HELIOS_ALLOW_NETWORK": "allow_network",
    "HELIOS_STRICT_BACKENDS": "strict_backends",
    "HELIOS_TOP_K": "top_k",
    "HELIOS_RERANK_TOP_N": "rerank_top_n",
    "HELIOS_CHUNK_SIZE": "chunk_size",
    "HELIOS_CHUNK_OVERLAP": "chunk_overlap",
}

#: 嵌套 YAML 的键名别名（network.allow -> allow_network 等）。
SECTION_ALIASES: dict[str, dict[str, str]] = {
    "network": {"allow": "allow_network"},
    "tools": {"calculator": "enable_calculator"},
}

#: 确定性视图中需要剔除的墙钟 / 延迟字段。
VOLATILE_FIELDS: frozenset[str] = frozenset(
    {"loaded_at", "created_at", "timestamp", "elapsed_ms", "latency_p50_ms", "latency_p95_ms", "wall_clock_ms"}
)

__all__ = ["PROFILE_BACKENDS", "INT_FIELDS", "ENV_FIELDS", "SECTION_ALIASES", "VOLATILE_FIELDS"]
