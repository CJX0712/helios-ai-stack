# 作者：晨星
"""文本与 PDF 解析：把原始输入归一化为 Document（ARCH §3.1 / M02）。

去重依据为归一化文本的 blake2b 内容哈希；同一份内容两次摄入得到同一 doc_id。
"""

from __future__ import annotations

import io

from ..core import codes
from ..core.errors import BadInputError, raise_for
from ..core.hashing import content_hash, doc_id_for
from ..core.text import normalize_text
from ..core.types import Document


_MIME_TEXT = ("text/plain", "text/markdown", "text/x-markdown", "application/markdown")
_MIME_PDF = ("application/pdf",)


def parse_text(text: str, source: str = "", mime: str = "text/plain") -> Document:
    """把纯文本 / Markdown 解析为 Document。

    Args:
        text: 原始文本。
        source: 来源标识（文件路径或 URL），用于派生稳定 doc_id。
        mime: 媒体类型。

    Returns:
        校验通过的 Document；空文本抛 ``E_INGEST_EMPTY_CORPUS``。
    """
    if not text or not text.strip():
        raise raise_for(codes.E_INGEST_EMPTY_CORPUS, message="空文本不可摄入", detail={"source": source})
    clean = text.strip()
    normalized = normalize_text(clean)
    return Document(
        doc_id=doc_id_for(clean, source),
        source=source or "<inline>",
        mime=mime,
        content_hash=content_hash(clean),
        text=clean,
        meta={"normalized_len": str(len(normalized))},
    )


def parse_pdf_bytes(data: bytes, source: str = "") -> Document:
    """把 PDF 字节流解析为纯文本 Document（使用 pypdf，零额外依赖）。

    需要 ``pypdf``；缺失时抛 ``E_INGEST_PARSE_FAILED``。
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - 依赖缺失分支
        raise raise_for(
            codes.E_INGEST_PARSE_FAILED, message="pypdf 不可用", detail={"error": str(exc)}
        ) from exc
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(p.strip() for p in pages if p.strip())
    except Exception as exc:  # pypdf 解析异常
        raise raise_for(
            codes.E_INGEST_PARSE_FAILED, message="PDF 解析失败", detail={"source": source, "error": str(exc)}
        ) from exc
    if not text.strip():
        raise raise_for(codes.E_INGEST_EMPTY_CORPUS, message="PDF 提取为空", detail={"source": source})
    clean = text.strip()
    return Document(
        doc_id=doc_id_for(clean, source),
        source=source or "<pdf>",
        mime="application/pdf",
        content_hash=content_hash(clean),
        text=clean,
        pages=max(1, len(pages)),
        meta={"normalized_len": str(len(normalize_text(clean)))},
    )


def parse_path(path: str) -> Document:
    """按扩展名分派解析器，读取本地文件为 Document。"""
    lower = path.lower()
    if lower.endswith(".pdf"):
        with open(path, "rb") as handle:
            return parse_pdf_bytes(handle.read(), source=path)
    if lower.endswith((".txt", ".md", ".markdown")):
        with open(path, encoding="utf-8") as handle:
            return parse_text(handle.read(), source=path, mime=_mime_for(path))
    raise BadInputError(message="不支持的扩展名", detail={"path": path})


def _mime_for(path: str) -> str:
    if path.lower().endswith((".md", ".markdown")):
        return "text/markdown"
    return "text/plain"
