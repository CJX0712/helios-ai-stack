# 作者：晨星
"""融合层（M07）：稠密 + 稀疏通路合并（ARCH §7 / C5）。"""

from .fuser import Fuser, reciprocal_rank_fusion


__all__ = ["Fuser", "reciprocal_rank_fusion"]
