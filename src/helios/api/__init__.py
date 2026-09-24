# 作者：晨星
"""接口层（M14）：HTTP / SSE 服务（ARCH §7 / C5）。"""

from .app import create_app, run_server


__all__ = ["create_app", "run_server"]
