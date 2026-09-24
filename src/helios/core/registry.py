# 作者：晨星
"""profile -> 实现的**唯一工厂**（ARCH C5 / §6）：换实现只改一行配置，业务代码零改动。

约定：
    * 每个后端以 ``BackendSpec(module, cls)`` 登记，运行时用 importlib 惰性导入，
      因此 core 不依赖任何上层模块（ARCH §1.2 单向依赖）；
    * 实现类构造签名约定为 ``__init__(self, config: ProfileConfig)``；兼容零参构造。
"""

from __future__ import annotations

import importlib

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .config import ProfileConfig, configs_root
from .errors import HeliosError, InternalError, NotFoundError
from .protocols import CAPABILITIES, LLM, Embedder, LexicalIndex, Reranker, VectorIndex


@dataclass(frozen=True)
class BackendSpec:
    """一个后端实现的位置描述。"""

    module: str
    cls: str


#: 各能力的后端登记表；新增实现只需在此追加一行（或调用 :func:`register_backend`）。
DEFAULT_SPECS: dict[str, dict[str, BackendSpec]] = {}


def _spec_table() -> dict[str, dict[str, BackendSpec]]:
    """返回（惰性初始化的）后端登记表。"""
    if not DEFAULT_SPECS:
        DEFAULT_SPECS.update(
            {
                "embed": {
                    "hashing": BackendSpec("helios.embed.hashing", "HashingEmbedder"),
                    "onnx": BackendSpec("helios.embed.onnx_direct", "OnnxDirectEmbedder"),
                    "fastembed": BackendSpec("helios.embed.fastembed_backend", "FastembedBackend"),
                    "ollama": BackendSpec("helios.embed.ollama_backend", "OllamaEmbedder"),
                },
                "vector": {
                    "numpy": BackendSpec("helios.vector.numpy_index", "NumpyVectorIndex"),
                    "faiss": BackendSpec("helios.vector.faiss_index", "FaissVectorIndex"),
                },
                "lexical": {
                    "bm25": BackendSpec("helios.lexical.service", "Bm25Index"),
                    "inverted": BackendSpec("helios.lexical.inverted", "InvertedIndex"),
                },
                "rerank": {
                    "lexical": BackendSpec("helios.rerank.lexical", "LexicalReranker"),
                    "onnx": BackendSpec("helios.rerank.onnx", "OnnxReranker"),
                    "none": BackendSpec("helios.rerank.noop", "NoopReranker"),
                    "remote": BackendSpec("helios.rerank.remote", "RemoteReranker"),
                },
                "llm": {
                    "template": BackendSpec("helios.llm.template", "TemplateLLM"),
                    "llama_cpp": BackendSpec("helios.llm.llama_cpp_backend", "LlamaCppLLM"),
                    "ollama": BackendSpec("helios.llm.ollama_backend", "OllamaLLM"),
                    "openai": BackendSpec("helios.llm.openai_backend", "OpenAICompatLLM"),
                },
            }
        )
    return DEFAULT_SPECS


def register_backend(capability: str, name: str, module: str, cls: str) -> None:
    """登记（或覆盖）一个后端实现，供后续任务与三方扩展注入。"""
    if capability not in CAPABILITIES:
        raise NotFoundError(message=f"未知能力: {capability}", detail={"capability": capability})
    _spec_table()
    DEFAULT_SPECS.setdefault(capability, {})[name] = BackendSpec(module=module, cls=cls)


def available_backends(capability: str) -> tuple[str, ...]:
    """返回某能力已登记的全部后端名（顺序稳定）。"""
    table = _spec_table()
    if capability not in table:
        raise NotFoundError(message=f"未知能力: {capability}", detail={"capability": capability})
    return tuple(sorted(table[capability]))


def spec_for(capability: str, backend: str) -> BackendSpec:
    """取后端登记项；未登记时抛 ``E_CORE_NOT_FOUND``。"""
    table = _spec_table()
    entries = table.get(capability)
    if entries is None:
        raise NotFoundError(message=f"未知能力: {capability}", detail={"capability": capability})
    spec = entries.get(backend)
    if spec is None:
        raise NotFoundError(
            message=f"未登记的后端: {capability}/{backend}",
            detail={"capability": capability, "backend": backend, "available": sorted(entries)},
        )
    return spec


def resolve(capability: str, backend: str, config: ProfileConfig) -> Any:
    """导入并实例化一个后端；缺失模块或缺失类均抛 ``E_CORE_NOT_FOUND``。"""
    spec = spec_for(capability, backend)
    try:
        module = importlib.import_module(spec.module)
    except ImportError as exc:
        raise NotFoundError(
            message=f"后端模块不可用: {spec.module}",
            detail={"capability": capability, "backend": backend, "error": str(exc)},
        ) from exc
    try:
        factory: Callable[..., Any] = getattr(module, spec.cls)
    except AttributeError as exc:
        raise NotFoundError(
            message=f"后端类缺失: {spec.module}.{spec.cls}",
            detail={"capability": capability, "backend": backend},
        ) from exc
    return _instantiate(factory, config, capability, backend)


def _instantiate(factory: Callable[..., Any], config: ProfileConfig, capability: str, backend: str) -> Any:
    """按约定构造实例：优先 ``factory(config)``，其次 ``factory()``。"""
    try:
        return factory(config)
    except TypeError:
        try:
            return factory()
        except TypeError as exc:
            raise InternalError(
                message=f"后端构造失败: {capability}/{backend}",
                detail={"error": str(exc)},
            ) from exc


def _profile_yaml(profile: str) -> dict[str, Any]:
    """读取 ``configs/profile_<profile>.yaml``；缺失返回空字典。"""
    return _read_yaml(configs_root() / f"profile_{profile}.yaml")


def _read_yaml(path: Path) -> dict[str, Any]:
    """读取 YAML 映射；非映射或非法的输入一律视为空字典（注册表只读可选字段）。"""
    if not path.is_file():
        return {}
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def fallback_chain(capability: str, config: ProfileConfig) -> tuple[str, ...]:
    """返回该能力的后端尝试顺序：配置中的主后端 + YAML 里的 fallbacks（去重保序）。"""
    primary = getattr(config, f"{capability}_backend", "")
    section = _profile_yaml(config.profile).get(capability)
    chain: list[str] = []
    if primary:
        chain.append(str(primary))
    if isinstance(section, dict):
        for item in section.get("fallbacks", []) or []:
            name = str(item)
            if name not in chain:
                chain.append(name)
    return tuple(chain)


def build_any(capability: str, config: ProfileConfig) -> Any:
    """按 fallback 链依次尝试构造后端，返回首个成功者；全部失败抛 ``E_CORE_NOT_FOUND``。"""
    errors: list[dict[str, str]] = []
    for backend in fallback_chain(capability, config):
        try:
            return resolve(capability, backend, config)
        except (HeliosError, NotFoundError, InternalError, ImportError, AttributeError) as exc:
            errors.append({"backend": backend, "error": str(exc)})
    raise NotFoundError(
        message=f"{capability} 无可用后端实现",
        detail={"capability": capability, "profile": config.profile, "errors": errors},
    )


def build_embedder(config: ProfileConfig) -> Embedder:
    """构造 Embedder。"""
    return build_any("embed", config)


def build_vector(config: ProfileConfig) -> VectorIndex:
    """构造 VectorIndex。"""
    return build_any("vector", config)


def build_lexical(config: ProfileConfig) -> LexicalIndex:
    """构造 LexicalIndex。"""
    return build_any("lexical", config)


def build_reranker(config: ProfileConfig) -> Reranker:
    """构造 Reranker。"""
    return build_any("rerank", config)


def build_llm(config: ProfileConfig) -> LLM:
    """构造 LLM。"""
    return build_any("llm", config)
