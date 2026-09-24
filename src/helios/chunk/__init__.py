# 作者：晨星
"""语块切分层（M03）：heading-aware 切分 + 定长打包（ARCH §3.2 / F-7）。"""

from .service import ChunkService
from .sizer import size_blocks
from .splitter import Block, split_blocks


__all__ = ["ChunkService", "size_blocks", "split_blocks", "Block"]
