# 作者：晨星
"""三档 profile 配置：YAML 加载 + ``HELIOS_*`` 环境变量覆盖 + 校验（ARCH §6）。

加载顺序：内置默认值 -> ``configs/default.yaml`` -> ``configs/profile_<profile>.yaml``
-> ``HELIOS_CONFIG`` 指定文件 -> ``HELIOS_*`` 环境变量。

``deterministic_view()`` 剔除墙钟字段，供测试做稳定断言；``fingerprint()`` 供缓存取键。
"""

from __future__ import annotations

import dataclasses
import os

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from .errors import ConfigInvalidError
from .hashing import stable_key
from .profile_spec import (
    ENV_FIELDS,
    INT_FIELDS,
    SECTION_ALIASES,
    VOLATILE_FIELDS,
)
from .types import utc_now_iso


#: 环境变量前缀（ARCH §6.1）。
ENV_PREFIX: str = "HELIOS_"

#: 合法 profile 档位。
PROFILES: tuple[str, ...] = ("offline", "local", "remote")

#: 合法日志级别。
LOG_LEVELS: frozenset[str] = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})

#: 后端绑定 / 字段表见 profile_spec.py（从本文件析出以控制单文件行数，ARCH §6）。


def configs_root() -> Path:
    """返回 ``configs/`` 目录（本文件位于 <root>/src/helios/core/ 下）。"""
    return Path(__file__).resolve().parents[3] / "configs"


def repo_root() -> Path:
    """返回仓库根目录。"""
    return Path(__file__).resolve().parents[3]


def _flatten(mapping: Mapping[str, Any]) -> dict[str, Any]:
    """把嵌套 YAML 摊平成字段名 -> 值的字典；``fallbacks`` 列表跳过（由 registry 读原始 YAML）。"""
    flat: dict[str, Any] = {}
    for section, body in mapping.items():
        if not isinstance(body, Mapping):
            flat[str(section)] = body
            continue
        for key, value in body.items():
            if key == "fallbacks":
                continue
            alias = SECTION_ALIASES.get(str(section), {}).get(str(key))
            flat[alias or f"{section}_{key}"] = value
    return flat


def _read_yaml(path: Path) -> dict[str, Any]:
    """读取 YAML 文件；文件不存在返回空字典，解析失败抛 ``E_CORE_CONFIG_INVALID``。"""
    if not path.is_file():
        return {}
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigInvalidError(message=f"YAML 解析失败: {path}", detail={"error": str(exc)}) from exc
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ConfigInvalidError(message=f"YAML 顶层必须是映射: {path}", detail={"path": str(path)})
    return loaded


@dataclasses.dataclass(frozen=True)
class ProfileConfig:
    """一份完整运行配置（frozen，所有覆盖都返回新实例）。"""

    profile: str = "offline"
    embed_backend: str = "hashing"
    embed_model: str = ""
    embed_dim: int = 384
    vector_backend: str = "numpy"
    lexical_backend: str = "bm25"
    rerank_backend: str = "lexical"
    rerank_model: str = ""
    llm_backend: str = "template"
    llm_model: str = ""
    llm_threads: int = 4
    llm_ctx: int = 4096
    top_k: int = 5
    rerank_top_n: int = 20
    candidate_multiplier: int = 4
    chunk_size: int = 600
    chunk_overlap: int = 80
    min_chunk_chars: int = 24
    embed_batch_size: int = 32
    allow_network: int = 0
    strict_backends: int = 0
    enable_calculator: int = 1
    log_level: str = "INFO"
    model_dir: str = "models/"
    data_dir: str = "data/"
    index_dir: str = "data/index"
    cache_dir: str = "data/cache"
    ollama_host: str = "http://127.0.0.1:11434"
    timeout_search_ms: int = 2000
    timeout_llm_ms: int = 120000
    config_path: str = ""
    source_paths: tuple[str, ...] = dataclasses.field(default_factory=tuple)
    loaded_at: str = dataclasses.field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """全字段校验，任一非法即抛 ``E_CORE_CONFIG_INVALID``。"""
        self._check(self.profile in PROFILES, "profile 必须是 offline/local/remote", field="profile")
        self._check(self.embed_dim > 0, "embed_dim 必须为正", field="embed_dim")
        self._check(self.llm_threads >= 1, "llm_threads 必须 >= 1", field="llm_threads")
        self._check(self.llm_ctx > 0, "llm_ctx 必须为正", field="llm_ctx")
        self._check(self.top_k >= 1, "top_k 必须 >= 1", field="top_k")
        self._check(self.rerank_top_n >= 1, "rerank_top_n 必须 >= 1", field="rerank_top_n")
        self._check(self.candidate_multiplier >= 1, "candidate_multiplier 必须 >= 1", field="candidate_multiplier")
        self._check(self.chunk_size >= 1, "chunk_size 必须为正", field="chunk_size")
        self._check(
            0 <= self.chunk_overlap < self.chunk_size,
            "chunk_overlap 必须落在 [0, chunk_size)",
            field="chunk_overlap",
        )
        self._check(self.timeout_search_ms > 0, "timeout_search_ms 必须为正", field="timeout_search_ms")
        self._check(self.timeout_llm_ms > 0, "timeout_llm_ms 必须为正", field="timeout_llm_ms")
        self._check(self.log_level.upper() in LOG_LEVELS, "log_level 非法", field="log_level")
        self._check(self.allow_network in (0, 1), "allow_network 只能是 0 或 1", field="allow_network")
        self._check(self.strict_backends in (0, 1), "strict_backends 只能是 0 或 1", field="strict_backends")
        self.log_level_value()

    def _check(self, condition: bool, message: str, **detail: Any) -> None:
        """校验失败即抛 ``E_CORE_CONFIG_INVALID``。"""
        if not condition:
            raise ConfigInvalidError(message=message, detail=detail)

    def log_level_value(self) -> str:
        """返回大写日志级别（大小写不敏感输入的归一出口）。"""
        return self.log_level.upper()

    def deterministic_view(self) -> dict[str, Any]:
        """返回剔除墙钟 / 延迟字段后的确定性视图，供断言与缓存取键。"""
        full = dataclasses.asdict(self)
        return {key: value for key, value in full.items() if key not in VOLATILE_FIELDS}

    def fingerprint(self) -> str:
        """返回确定性视图的稳定哈希（配置变更即缓存失效）。"""
        return stable_key("ProfileConfig", **self.deterministic_view())

    def with_overrides(self, **fields: Any) -> ProfileConfig:
        """返回应用覆盖后的新实例（原实例不变）。"""
        return dataclasses.replace(self, **fields)

    def to_dict(self) -> dict[str, Any]:
        """完整序列化（含墙钟字段）。"""
        return dataclasses.asdict(self)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> ProfileConfig:
        """按完整加载链构造配置：内置默认 -> default.yaml -> profile yaml -> 环境变量。

        Args:
            env: 环境变量视图；None 表示使用 :data:`os.environ`。

        Returns:
            校验通过的 :class:`ProfileConfig`。
        """
        source = os.environ if env is None else env
        raw: dict[str, Any] = {}
        paths: list[str] = []

        default_path = configs_root() / "default.yaml"
        raw.update(_flatten(_read_yaml(default_path)))
        if default_path.is_file():
            paths.append(str(default_path))

        profile = str(source.get("HELIOS_PROFILE", raw.get("profile", "offline"))).strip() or "offline"
        profile_path = configs_root() / f"profile_{profile}.yaml"
        raw.update(_flatten(_read_yaml(profile_path)))
        if profile_path.is_file():
            paths.append(str(profile_path))

        explicit = str(source.get("HELIOS_CONFIG", "")).strip()
        if explicit:
            explicit_path = Path(explicit)
            if not explicit_path.is_file():
                raise ConfigInvalidError(message=f"HELIOS_CONFIG 指向的文件不存在: {explicit}")
            raw.update(_flatten(_read_yaml(explicit_path)))
            paths.append(str(explicit_path))

        allowed = {field.name for field in dataclasses.fields(cls)}
        for env_name, field_name in ENV_FIELDS.items():
            if env_name in source and source[env_name] != "":
                raw[field_name] = source[env_name]

        typed: dict[str, Any] = {}
        for key, value in raw.items():
            if key not in allowed:
                continue
            typed[key] = _coerce(key, value)
        typed.setdefault("source_paths", tuple(paths))
        return cls(**typed)

    @classmethod
    def load(cls, path: str | Path, env: Mapping[str, str] | None = None) -> ProfileConfig:
        """以指定 YAML 为覆盖源构造配置；随后仍应用环境变量覆盖。"""
        source = os.environ if env is None else dict(env)
        merged = dict(source)
        merged["HELIOS_CONFIG"] = str(path)
        return cls.from_env(merged)


def _coerce(field_name: str, value: Any) -> Any:
    """按字段类型把 YAML / 环境变量字符串转成目标类型。"""
    if field_name in INT_FIELDS:
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ConfigInvalidError(message=f"{field_name} 必须是整数", detail={"value": value}) from exc
    return value
