# 作者：晨星
"""CLI 入口模块：支持 ``python -m helios.cli``（ARCH §7 / T11）。"""

from __future__ import annotations

from .main import main


if __name__ == "__main__":
    raise SystemExit(main())
