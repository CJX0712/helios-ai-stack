# 作者：晨星
"""helios —— 无 GPU Windows 机器上可离线一键复现的模块化端到端 RAG 系统。

包名 ``helios``（项目名 ``helios-ai-stack``），源码根 ``src/helios/``（ARCH C1 / U1）。
"""

from . import core


__version__: str = "0.1.0"
__author__: str = "晨星"

__all__: list[str] = ["core", "__version__", "__author__"]
