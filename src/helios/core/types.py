# 作者：晨星
"""helios 全局数据契约（ARCH §8.1）。

所有跨模块通信一律使用本文件的 frozen dataclass，禁止直接传递实现细节对象（ARCH C4）。
每个 dataclass 提供 ``to_dict`` / ``from_dict`` 以支持持久化与断言用的序列化往返。
"""

from __future__ import annotations

import dataclasses
import math

from datetime import UTC, datetime
from typing import Any

from .errors import BadInputError
from .serde import _build


#: Hit.source 的合法取值（稠密通路 / 稀疏通路 / 融合后）。
HIT_SOURCES: frozenset[str] = frozenset({"dense", "sparse", "fused"})

#: ScoredChunk.stage 的合法取值（融合后 / 重排后）。
SCORED_STAGES: frozenset[str] = frozenset({"fused", "reranked"})


def utc_now_iso() -> str:
    """返回 ISO 8601 UTC 时间戳字符串（秒级精度，末尾 Z）。"""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _require(condition: bool, message: str, **detail: Any) -> None:
    """契约校验失败即抛 ``E_CORE_BAD_INPUT``，detail 携带具体字段。"""
    if not condition:
        raise BadInputError(message=message, detail=detail)


def _is_number(value: Any) -> bool:
    """判断值是否为有限数值（bool 不算数值）。"""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


@dataclasses.dataclass(frozen=True)
class Document:
    """一份原始文档（解析后的纯文本形态）。"""

    doc_id: str
    source: str
    mime: str
    content_hash: str
    text: str
    pages: int = 1
    meta: dict[str, str] = dataclasses.field(default_factory=dict)
    created_at: str = dataclasses.field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        _require(bool(self.doc_id), "doc_id 不能为空", field="doc_id")
        _require(bool(self.content_hash), "content_hash 不能为空", field="content_hash")
        _require(self.pages >= 0, "pages 不能为负", field="pages", value=self.pages)

    def to_dict(self) -> dict[str, Any]:
        """序列化为普通 dict。"""
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Document:
        """由 dict 还原；未知字段忽略。"""
        return _build(cls, data)


@dataclasses.dataclass(frozen=True)
class Chunk:
    """文档内的一块文本，带原文 span 与标题路径快照（ARCH F-7）。"""

    chunk_id: str
    doc_id: str
    ordinal: int
    text: str
    span_start: int = 0
    span_end: int = 0
    heading_path: tuple[str, ...] = dataclasses.field(default_factory=tuple)
    token_estimate: int = 0

    def __post_init__(self) -> None:
        _require(bool(self.chunk_id), "chunk_id 不能为空", field="chunk_id")
        _require(self.ordinal >= 0, "ordinal 不能为负", field="ordinal", value=self.ordinal)
        _require(self.span_start >= 0, "span_start 不能为负", field="span_start", value=self.span_start)
        _require(self.span_end >= self.span_start, "span_end 必须 >= span_start", field="span_end")
        _require(self.token_estimate >= 0, "token_estimate 不能为负", field="token_estimate")

    @property
    def span(self) -> tuple[int, int]:
        """以 ``(start, end)`` 形式返回字符区间。"""
        return (self.span_start, self.span_end)

    def to_dict(self) -> dict[str, Any]:
        """序列化为普通 dict。"""
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Chunk:
        """由 dict 还原；heading_path 的 list 会被归一为 tuple。"""
        return _build(cls, data)


@dataclasses.dataclass(frozen=True)
class Hit:
    """单条检索命中，保留本通路位次与跨通路位次（供融合与诊断）。"""

    chunk_id: str
    score: float
    source: str = "fused"
    rank: int = 1
    dense_rank: int | None = None
    sparse_rank: int | None = None
    fused_score: float | None = None

    def __post_init__(self) -> None:
        _require(bool(self.chunk_id), "chunk_id 不能为空", field="chunk_id")
        _require(_is_number(self.score), "score 必须是有限数值", field="score", value=self.score)
        _require(self.source in HIT_SOURCES, "source 非法", field="source", value=self.source)
        _require(self.rank >= 1, "rank 从 1 开始", field="rank", value=self.rank)
        for name, value in (("dense_rank", self.dense_rank), ("sparse_rank", self.sparse_rank)):
            if value is not None:
                _require(value >= 1, f"{name} 从 1 开始", field=name, value=value)

    def to_dict(self) -> dict[str, Any]:
        """序列化为普通 dict。"""
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Hit:
        """由 dict 还原。"""
        return _build(cls, data)


@dataclasses.dataclass(frozen=True)
class ScoredChunk:
    """带分数的候选块，记录重排前后的位次变化（ARCH §9 序位可断言）。"""

    chunk: Chunk
    score: float
    stage: str = "fused"
    rank_before: int = 1
    rank_after: int = 1

    def __post_init__(self) -> None:
        _require(isinstance(self.chunk, Chunk), "chunk 必须是 Chunk", field="chunk")
        _require(_is_number(self.score), "score 必须是有限数值", field="score", value=self.score)
        _require(self.stage in SCORED_STAGES, "stage 非法", field="stage", value=self.stage)
        _require(self.rank_before >= 1, "rank_before 从 1 开始", field="rank_before")
        _require(self.rank_after >= 1, "rank_after 从 1 开始", field="rank_after")

    def to_dict(self) -> dict[str, Any]:
        """序列化为普通 dict（嵌套 chunk 一并展开）。"""
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScoredChunk:
        """由 dict 还原（嵌套 chunk 递归还原）。"""
        return _build(cls, data)


@dataclasses.dataclass(frozen=True)
class Citation:
    """一条可回溯引用：答案片段 -> chunk -> 原文 span。"""

    citation_id: str
    chunk_id: str
    doc_id: str
    span_start: int = 0
    span_end: int = 0
    quote: str = ""
    score: float = 0.0

    def __post_init__(self) -> None:
        _require(bool(self.citation_id), "citation_id 不能为空", field="citation_id")
        _require(bool(self.chunk_id), "chunk_id 不能为空", field="chunk_id")
        _require(self.span_end >= self.span_start, "span_end 必须 >= span_start", field="span_end")
        _require(_is_number(self.score), "score 必须是有限数值", field="score", value=self.score)

    def to_dict(self) -> dict[str, Any]:
        """序列化为普通 dict。"""
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Citation:
        """由 dict 还原。"""
        return _build(cls, data)


@dataclasses.dataclass(frozen=True)
class Answer:
    """一次 query 的最终产物，含引用、耗时埋点、降级标记与后端自检。"""

    query: str
    text: str
    citations: tuple[Citation, ...] = dataclasses.field(default_factory=tuple)
    timings: dict[str, float] = dataclasses.field(default_factory=dict)
    trace_id: str = ""
    profile: str = "offline"
    degraded: tuple[str, ...] = dataclasses.field(default_factory=tuple)
    diagnostics: dict[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        _require(isinstance(self.query, str), "query 必须是字符串", field="query")
        for name, value in self.timings.items():
            _require(_is_number(value) and float(value) >= 0.0, f"timings[{name}] 必须是非负数值", field=name)
        for citation in self.citations:
            _require(isinstance(citation, Citation), "citations 元素必须是 Citation", field="citations")

    def has_citation(self) -> bool:
        """是否存在至少一条可回溯引用（P0-5 判据）。"""
        return len(self.citations) > 0

    def to_dict(self) -> dict[str, Any]:
        """序列化为普通 dict。"""
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Answer:
        """由 dict 还原（citations 递归还原）。"""
        return _build(cls, data)


@dataclasses.dataclass(frozen=True)
class MetricsReport:
    """一档评测的结果报告（文档级为头条指标，块级仅诊断，ARCH F-3）。"""

    profile: str
    baseline: str
    query_count: int
    recall_at_5: float = 0.0
    recall_at_10: float = 0.0
    mrr: float = 0.0
    ndcg_at_10: float = 0.0
    doc_hit_rate: float = 0.0
    doc_mrr: float = 0.0
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    created_at: str = dataclasses.field(default_factory=utc_now_iso)

    def __post_init__(self) -> None:
        _require(self.query_count >= 0, "query_count 不能为负", field="query_count")
        _require(self.baseline != "", "baseline 不能为空", field="baseline")
        for name in ("recall_at_5", "recall_at_10", "mrr", "ndcg_at_10", "doc_hit_rate", "doc_mrr"):
            value = getattr(self, name)
            _require(_is_number(value) and 0.0 <= float(value) <= 1.0, f"{name} 必须落在 [0, 1]", field=name)

    def to_dict(self) -> dict[str, Any]:
        """序列化为普通 dict。"""
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MetricsReport:
        """由 dict 还原。"""
        return _build(cls, data)


@dataclasses.dataclass(frozen=True)
class IngestStats:
    """一次摄入的统计结果（docs/chunks/ms）。"""

    doc_count: int = 0
    chunk_count: int = 0
    skipped_duplicates: int = 0
    elapsed_ms: float = 0.0

    def __post_init__(self) -> None:
        _require(self.doc_count >= 0, "doc_count 不能为负", field="doc_count")
        _require(self.chunk_count >= 0, "chunk_count 不能为负", field="chunk_count")
        _require(self.skipped_duplicates >= 0, "skipped_duplicates 不能为负", field="skipped_duplicates")
        _require(float(self.elapsed_ms) >= 0.0, "elapsed_ms 不能为负", field="elapsed_ms")

    def to_dict(self) -> dict[str, Any]:
        """序列化为普通 dict。"""
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IngestStats:
        """由 dict 还原。"""
        return _build(cls, data)
