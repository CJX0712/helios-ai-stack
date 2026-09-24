# 作者：晨星
"""IngestService: 文本 -> Document，按内容哈希幂等去重（ARCH §3.1 / M02）。

去重依据为归一化文本的 blake2b 内容哈希；同一份内容两次摄入得到同一 doc_id 且只计一次。
"""

from __future__ import annotations

import dataclasses

from ..core.hashing import content_hash, doc_id_for
from ..core.text import normalize_text
from ..core.types import Document, IngestStats


class IngestService:
    """把原始文本归一化为 Document，并按内容哈希去重。"""

    def __init__(self) -> None:
        self._hashes: set[str] = set()
        self._stats = IngestStats()

    def ingest(self, text: str, source: str = "") -> Document | None:
        """摄入一段文本；重复内容返回 ``None`` 并累加 skipped_duplicates。"""
        if not text or not text.strip():
            return None
        clean = text.strip()
        digest = content_hash(clean)
        if digest in self._hashes:
            self._stats = dataclasses.replace(
                self._stats, skipped_duplicates=self._stats.skipped_duplicates + 1
            )
            return None
        self._hashes.add(digest)
        doc = Document(
            doc_id=doc_id_for(clean, source),
            source=source or "<inline>",
            mime="text/plain",
            content_hash=digest,
            text=clean,
            meta={"normalized_len": str(len(normalize_text(clean)))},
        )
        self._stats = dataclasses.replace(self._stats, doc_count=self._stats.doc_count + 1)
        return doc

    def ingest_many(self, items: list[tuple[str, str]]) -> IngestStats:
        """批量摄入 ``(text, source)`` 列表，返回累计统计。"""
        for text, source in items:
            self.ingest(text, source)
        return self.stats()

    def stats(self) -> IngestStats:
        """返回当前累计统计（副本）。"""
        return self._stats

    def reset(self) -> None:
        """清空去重集合与统计。"""
        self._hashes.clear()
        self._stats = IngestStats()
