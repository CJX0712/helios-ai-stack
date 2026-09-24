# 作者：晨星
"""追踪与埋点：trace_id、阶段耗时、loguru 结构化日志（ARCH P1-6）。

``Tracer`` 只保留**可断言的阶段耗时**，不持有墙钟时间戳，便于确定性断言。
"""

from __future__ import annotations

import contextlib
import sys
import time
import uuid

from collections.abc import Iterator
from typing import Any

from loguru import logger

from .types import utc_now_iso


#: 默认日志级别。
DEFAULT_LOG_LEVEL: str = "INFO"

#: 结构化日志格式（不含 emoji，避免 GBK mangled，ARCH F-18）。
LOG_FORMAT: str = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | "
    "{extra[trace_id]} | {message}"
)


def new_trace_id() -> str:
    """生成短 trace_id，形如 ``trc-<16 位十六进制>``。"""
    return "trc-" + uuid.uuid4().hex[:16]


def configure_logging(level: str = DEFAULT_LOG_LEVEL, sink: Any = None) -> None:
    """配置 loguru 输出；可重复调用（幂等，先清空再挂载）。"""
    logger.remove()
    logger.add(sink if sink is not None else sys.stderr, level=level.upper(), format=LOG_FORMAT)
    logger.configure(extra={"trace_id": "-"})


def bound_logger(trace_id: str = "") -> Any:
    """返回绑定 trace_id 的 logger，供各阶段打点。"""
    return logger.bind(trace_id=trace_id or "-")


class Tracer:
    """阶段耗时收集器。

    Attributes:
        trace_id: 本次调用链标识。
        profile: 档位名，便于日志聚合。
    """

    def __init__(self, trace_id: str | None = None, profile: str = "offline") -> None:
        self.trace_id: str = trace_id or new_trace_id()
        self.profile: str = profile
        self._timings: dict[str, float] = {}
        self._logger: Any = bound_logger(self.trace_id)

    @contextlib.contextmanager
    def stage(self, name: str) -> Iterator[None]:
        """以上下文管理器方式记录一个阶段的耗时（毫秒）。"""
        started = time.perf_counter()
        try:
            yield
        finally:
            self.record(name, (time.perf_counter() - started) * 1000.0)

    def record(self, name: str, elapsed_ms: float) -> None:
        """显式登记一个阶段耗时；同名阶段累加（便于重试场景）。"""
        self._timings[name] = self._timings.get(name, 0.0) + float(elapsed_ms)

    def timings(self) -> dict[str, float]:
        """返回阶段耗时快照（副本，避免外部篡改内部状态）。"""
        return dict(self._timings)

    def total_ms(self) -> float:
        """返回已登记阶段耗时之和。"""
        return float(sum(self._timings.values()))

    def reset(self) -> None:
        """清空已登记的耗时（复用 Tracer 时使用）。"""
        self._timings.clear()

    def log(self, event: str, **fields: Any) -> None:
        """打一条结构化日志，自动附带 trace_id 与 profile。"""
        payload = " ".join(f"{key}={value}" for key, value in sorted(fields.items()))
        suffix = f" | {payload}" if payload else ""
        self._logger.info(f"event={event} profile={self.profile}{suffix}")

    def as_diagnostics(self) -> dict[str, Any]:
        """输出可放进 ``Answer.diagnostics`` 的追踪摘要（不含墙钟字段）。"""
        return {"trace_id": self.trace_id, "profile": self.profile, "timings_ms": self.timings()}


def wall_clock_now() -> str:
    """返回当前 UTC 时间戳（仅在确实需要墙钟处调用，不进确定性视图）。"""
    return utc_now_iso()
