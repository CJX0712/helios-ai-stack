# 作者：晨星
"""helios 异常体系（ARCH C6）。

全部异常继承 ``HeliosError(code, message, detail)``，HTTP 层由 ``api/error_handler.py``
经 :meth:`HeliosError.to_http` 映射，响应体含 ``error.code``。
"""

from __future__ import annotations

from typing import Any

from . import codes


class HeliosError(Exception):
    """helios 全部异常的基类。

    Attributes:
        code: ``E_<MODULE>_<REASON>`` 形式的错误码，必须已登记于 :mod:`helios.core.codes`。
        message: 面向人的简短说明。
        detail: 结构化上下文，供排障与日志使用，必须可 JSON 序列化。
        recoverable: 是否可通过修配置 / 换后端 / 重试恢复。
    """

    default_code: str = codes.E_CORE_INTERNAL

    def __init__(
        self,
        code: str | None = None,
        message: str = "",
        detail: dict[str, Any] | None = None,
        recoverable: bool | None = None,
    ) -> None:
        resolved = code or self.default_code
        super().__init__(resolved if not message else f"{resolved}: {message}")
        self.code: str = resolved
        self.message: str = message or resolved
        self.detail: dict[str, Any] = dict(detail or {})
        self.recoverable: bool = codes.default_recoverable(resolved) if recoverable is None else recoverable

    def to_dict(self) -> dict[str, Any]:
        """序列化为响应体中的 ``error`` 对象。"""
        return {
            "code": self.code,
            "message": self.message,
            "detail": self.detail,
            "recoverable": self.recoverable,
        }

    def to_http(self) -> tuple[int, dict[str, Any]]:
        """映射为 ``(http_status, body)``，body 形如 ``{"error": {...}}``。"""
        status = codes.http_status(self.code)
        return status, {"error": self.to_dict()}

    def with_detail(self, **fields: Any) -> HeliosError:
        """补充 detail 字段并返回自身，便于链式记录上下文。"""
        self.detail.update(fields)
        return self


class BadInputError(HeliosError):
    """入参类型或取值非法。"""

    default_code = codes.E_CORE_BAD_INPUT


class NotFoundError(HeliosError):
    """资源不存在（id 未登记、后端未实现等）。"""

    default_code = codes.E_CORE_NOT_FOUND


class ConfigInvalidError(BadInputError):
    """配置缺键或取值非法，需修配置后重启。"""

    default_code = codes.E_CORE_CONFIG_INVALID


class NetworkDisabledError(HeliosError):
    """``HELIOS_ALLOW_NETWORK=0`` 时发起外网请求（ARCH F-11）。"""

    default_code = codes.E_CORE_INTERNAL

    def __init__(
        self,
        component: str = "core",
        url: str = "",
        message: str = "",
        detail: dict[str, Any] | None = None,
    ) -> None:
        code = codes.net_disabled_code(component)
        text = message or f"网络闸门关闭，禁止访问 {url or '外部地址'}"
        merged = dict(detail or {})
        merged.setdefault("component", component)
        merged.setdefault("url", url)
        super().__init__(code=code, message=text, detail=merged, recoverable=True)


class HeliosTimeoutError(HeliosError):
    """阶段超时；可重试或降批。"""

    default_code = codes.E_PIPE_TIMEOUT


class InternalError(HeliosError):
    """未分类内核异常。"""

    default_code = codes.E_CORE_INTERNAL


def raise_for(
    code: str,
    message: str = "",
    detail: dict[str, Any] | None = None,
    recoverable: bool | None = None,
) -> HeliosError:
    """按错误码返回待抛出的异常实例（供 ``raise raise_for(...)`` 使用）。"""
    return HeliosError(code=code, message=message, detail=detail, recoverable=recoverable)
