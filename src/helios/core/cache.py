# 作者：晨星
"""结果缓存：diskcache 落盘缓存，按「query + 配置指纹」取键（ARCH P1-5）。

缓存键由 :func:`helios.core.hashing.stable_key` 生成，配置参数进入键的一部分，
因此换 profile / top_k 会自然失效。``enabled=False`` 时整体退化为空操作（不落盘）。
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .errors import InternalError
from .hashing import stable_key


#: 默认缓存目录。
DEFAULT_CACHE_DIR: str = "data/cache"

#: 默认命名空间，避免与其它应用共用目录冲突。
DEFAULT_NAMESPACE: str = "helios"


class ResultCache:
    """diskcache -backed 结果缓存。

    Attributes:
        directory: 缓存落盘目录。
        namespace: 键前缀命名空间。
        ttl_seconds: 默认过期秒数；None 表示不过期。
        enabled: 总开关；False 时所有操作为空操作。
    """

    def __init__(
        self,
        directory: str | Path = DEFAULT_CACHE_DIR,
        namespace: str = DEFAULT_NAMESPACE,
        ttl_seconds: float | None = None,
        enabled: bool = True,
    ) -> None:
        self.directory: Path = Path(directory)
        self.namespace: str = namespace
        self.ttl_seconds: float | None = ttl_seconds
        self.enabled: bool = enabled
        self.hits: int = 0
        self.misses: int = 0
        self._cache: Any = None
        if self.enabled:
            self._cache = _open_diskcache(self.directory)

    def make_key(self, query: str, **params: Any) -> str:
        """按 query 与参数生成稳定缓存键（含命名空间前缀）。"""
        return f"{self.namespace}:{stable_key(query, **params)}"

    def get(self, key: str, default: Any = None) -> Any:
        """读取缓存；未命中或已过期返回 default。"""
        if not self.enabled or self._cache is None:
            self.misses += 1
            return default
        try:
            value = self._cache.get(key, default=default)
        except Exception as exc:  # 缓存介质损坏不应击穿主链路
            self.misses += 1
            raise InternalError(message="缓存读取失败", detail={"error": str(exc)}) from exc
        if value is default:
            self.misses += 1
            return default
        self.hits += 1
        return value

    def set(self, key: str, value: Any, ttl_seconds: float | None = None) -> bool:
        """写入缓存；返回是否真正写入。"""
        if not self.enabled or self._cache is None:
            return False
        expire = self.ttl_seconds if ttl_seconds is None else ttl_seconds
        try:
            return bool(self._cache.set(key, value, expire=expire))
        except Exception as exc:
            raise InternalError(message="缓存写入失败", detail={"error": str(exc)}) from exc

    def get_or_set(self, key: str, factory: Callable[[], Any], ttl_seconds: float | None = None) -> Any:
        """命中即返回，未命中则调用 factory 计算并回写。"""
        sentinel = object()
        cached = self.get(key, default=sentinel)
        if cached is not sentinel:
            return cached
        value = factory()
        self.set(key, value, ttl_seconds=ttl_seconds)
        return value

    def delete(self, key: str) -> bool:
        """删除单个键。"""
        if not self.enabled or self._cache is None:
            return False
        return bool(self._cache.delete(key))

    def clear(self) -> int:
        """清空缓存并返回被清理的条目数。"""
        if not self.enabled or self._cache is None:
            return 0
        count = int(len(self._cache))
        self._cache.clear()
        return count

    def invalidate(self, query: str, **params: Any) -> bool:
        """按 query + 参数反算出键并删除（配置变更后的精准失效）。"""
        return self.delete(self.make_key(query, **params))

    def stats(self) -> dict[str, int]:
        """返回命中/未命中计数与当前条目数。"""
        size = 0 if self._cache is None else int(len(self._cache))
        return {"hits": self.hits, "misses": self.misses, "size": size}

    def close(self) -> None:
        """关闭底层 diskcache 句柄。"""
        if self._cache is not None:
            self._cache.close()
            self._cache = None

    def __enter__(self) -> ResultCache:
        """支持 with 用法。"""
        return self

    def __exit__(self, *_exc: object) -> None:
        """退出 with 时自动关闭句柄。"""
        self.close()


def _open_diskcache(directory: Path) -> Any:
    """惰性导入 diskcache 并打开目录；缺依赖时抛 ``E_CORE_INTERNAL``。"""
    try:
        from diskcache import Cache
    except ImportError as exc:
        raise InternalError(message="diskcache 未安装，无法启用结果缓存", detail={"error": str(exc)}) from exc
    directory.mkdir(parents=True, exist_ok=True)
    return Cache(str(directory))
