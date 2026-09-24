# 作者：晨星
"""数据摄入层（M02）：把 TXT/MD/PDF 解析成 Document，按内容哈希去重。

只依赖 core，不 import 任何上层模块（ARCH §1.2 单向依赖）。
"""

from .parsers import parse_pdf_bytes, parse_text
from .service import IngestService


__all__ = ["IngestService", "parse_text", "parse_pdf_bytes"]
