# 作者：晨星
"""API 错误映射：把 HeliosError 统一转为含 error.code 的 JSON 响应（ARCH C6 / §5）。"""

from __future__ import annotations

from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse

from ..core.errors import HeliosError


async def helios_exception_handler(_: Request, exc: HeliosError) -> JSONResponse:
    """FastAPI / Starlette 异常处理器：返回 ``{"error": {...}}``。"""
    status, body = exc.to_http()
    return JSONResponse(status_code=status, content=body)


def register_error_handlers(app: Any) -> None:
    """把 HeliosError 处理器挂到 app 上（兼容 FastAPI 与裸 Starlette）。"""
    app.add_exception_handler(HeliosError, helios_exception_handler)
