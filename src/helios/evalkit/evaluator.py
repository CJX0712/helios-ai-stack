# 作者：晨星
"""评测引擎：文档级头条指标 + 三组对照基线（ARCH §7 / T14）。

基线：
    * ``pure_dense``：仅稠密通路；
    * ``pure_bm25``：仅词法通路；
    * ``hybrid_no_rerank``（B0）：融合但不重排；
    * ``hybrid_rerank``：融合 + 重排（默认主链路）。
头条指标：doc_hit_rate / doc_mrr；辅以 recall@5/@10、ndcg@10、p50/p95 延迟。
"""

from __future__ import annotations

import json
import statistics
import time

from pathlib import Path
from typing import Any

from ..core.config import ProfileConfig
from ..core.types import MetricsReport
from ..pipeline import Pipeline


def _load_gold(path: str) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return data.get("queries", [])
    return data


def _ndcg(relevance: list[int]) -> float:
    """标准 nDCG@k（k=len(relevance)），相关性为 0/1。"""
    dcg = 0.0
    for i, rel in enumerate(relevance, start=1):
        dcg += rel / (1.0 + __import__("math").log2(i))
    ideal = sorted(relevance, reverse=True)
    idcg = 0.0
    for i, rel in enumerate(ideal, start=1):
        idcg += rel / (1.0 + __import__("math").log2(i))
    return dcg / idcg if idcg > 0 else 0.0


def evaluate(
    pipeline: Pipeline,
    gold: list[dict[str, Any]],
    *,
    top_k: int = 5,
    mode: str = "hybrid",
    rerank: bool = True,
    profile: str = "offline",
    baseline: str = "hybrid_rerank",
) -> MetricsReport:
    """在单一 pipeline 上按给定 mode/rerank 跑评测，返回 MetricsReport。"""
    src_map = pipeline.doc_sources()
    hits: list[float] = []
    rranks: list[float] = []
    recalls5: list[float] = []
    recalls10: list[float] = []
    ndcgs: list[float] = []
    latencies: list[float] = []

    for item in gold:
        wanted = item.get("relevant", [])
        rel: set[str] = set()
        for w in wanted:
            for src, did in src_map.items():
                if src == w or src.endswith(w) or w.endswith(src):
                    rel.add(did)
        if not rel:
            continue
        t0 = time.perf_counter()
        results = pipeline.retrieve(item["query"], top_k=top_k, rerank=rerank, mode=mode)
        latencies.append((time.perf_counter() - t0) * 1000.0)
        retrieved = [sc.chunk.doc_id for sc in results]

        hit = any(d in rel for d in retrieved)
        hits.append(1.0 if hit else 0.0)
        rank = next((i for i, d in enumerate(retrieved, 1) if d in rel), None)
        rranks.append(1.0 / rank if rank else 0.0)
        recalls5.append(len(rel & set(retrieved[:5])) / len(rel))
        recalls10.append(len(rel & set(retrieved[:10])) / len(rel))
        ndcgs.append(_ndcg([1 if d in rel else 0 for d in retrieved[:10]]))

    p50 = statistics.median(latencies) if latencies else 0.0
    p95 = sorted(latencies)[int(0.95 * len(latencies)) - 1] if latencies else 0.0
    return MetricsReport(
        profile=profile,
        baseline=baseline,
        query_count=len(hits),
        recall_at_5=statistics.fmean(recalls5),
        recall_at_10=statistics.fmean(recalls10),
        mrr=statistics.fmean(rranks),
        ndcg_at_10=statistics.fmean(ndcgs),
        doc_hit_rate=statistics.fmean(hits),
        doc_mrr=statistics.fmean(rranks),
        latency_p50_ms=p50,
        latency_p95_ms=p95,
    )


def run_baselines(
    corpus_dir: str, gold_path: str, config: ProfileConfig, top_k: int = 5
) -> list[tuple[str, MetricsReport]]:
    """构建一次索引，跑四组基线并返回 ``(名称, 报告)`` 列表。"""
    pipe = Pipeline(config)
    items: list[tuple[str, str]] = []
    root = Path(corpus_dir)
    files = [root] if root.is_file() else list(root.rglob("*.md")) + list(root.rglob("*.txt"))
    for f in sorted(files):
        items.append((f.read_text(encoding="utf-8"), str(f)))
    pipe.add_documents(items)
    gold = _load_gold(gold_path)

    config_top_k = top_k or config.top_k
    specs = [
        ("pure_dense", {"mode": "dense", "rerank": False}),
        ("pure_bm25", {"mode": "sparse", "rerank": False}),
        ("hybrid_no_rerank", {"mode": "hybrid", "rerank": False}),
        ("hybrid_rerank", {"mode": "hybrid", "rerank": True}),
    ]
    reports: list[tuple[str, MetricsReport]] = []
    for name, kw in specs:
        rep = evaluate(pipe, gold, top_k=config_top_k, profile=config.profile, baseline=name, **kw)
        reports.append((name, rep))
    return reports


def compute_metrics(per_query: list[dict[str, Any]], k: int = 5) -> dict[str, float]:
    """从 ``[{retrieved:[doc_id...], relevant:[doc_id...]}]`` 直接计算文档级指标（轻量版）。"""
    hits, rranks, r5, r10, nd = [], [], [], [], []
    for q in per_query:
        rel = set(q["relevant"])
        ret = q["retrieved"][:k]
        hits.append(1.0 if any(d in rel for d in ret[:5]) else 0.0)
        rank = next((i for i, d in enumerate(ret, 1) if d in rel), None)
        rranks.append(1.0 / rank if rank else 0.0)
        r5.append(len(rel & set(ret[:5])) / len(rel))
        r10.append(len(rel & set(ret[:10])) / len(rel))
        nd.append(_ndcg([1 if d in rel else 0 for d in ret[:10]]))
    return {
        "doc_hit_rate": statistics.fmean(hits),
        "doc_mrr": statistics.fmean(rranks),
        "recall_at_5": statistics.fmean(r5),
        "recall_at_10": statistics.fmean(r10),
        "ndcg_at_10": statistics.fmean(nd),
    }
