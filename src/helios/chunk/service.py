# 作者：晨星
"""ChunkService: Document -> 有序 Chunk（ARCH §3.2 / M03）。"""

from __future__ import annotations

from ..core.hashing import chunk_id_for
from ..core.types import Chunk, Document
from .sizer import size_blocks
from .splitter import split_blocks


def _coerce_int(value: object, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


class ChunkService:
    """按 chunk_size / overlap 把文档切成有序语块，标题路径快照随块携带。"""

    def __init__(self, config: object | None = None) -> None:
        self._chunk_size = _coerce_int(getattr(config, "chunk_size", None), 600)
        self._overlap = _coerce_int(getattr(config, "chunk_overlap", None), 80)

    def chunk_document(self, doc: Document) -> list[Chunk]:
        """把单个 Document 切成 Chunk 列表（ordinal 从 0 递增）。"""
        blocks = split_blocks(doc.text)
        sized = size_blocks(blocks, self._chunk_size, self._overlap)
        chunks: list[Chunk] = []
        for ordinal, (text, heading, start, end) in enumerate(sized):
            chunks.append(
                Chunk(
                    chunk_id=chunk_id_for(doc.doc_id, ordinal),
                    doc_id=doc.doc_id,
                    ordinal=ordinal,
                    text=text,
                    span_start=max(0, start),
                    span_end=max(start, end),
                    heading_path=heading,
                    token_estimate=max(1, len(text) // 4),
                )
            )
        return chunks

    def chunk_text(self, text: str, doc_id: str) -> list[Chunk]:
        """直接对纯文本切块（doc_id 已派生）。"""
        from ..core.hashing import doc_id_for

        did = doc_id or doc_id_for(text)
        return self.chunk_document(Document(doc_id=did, source="<text>", mime="text/plain", content_hash="", text=text))
