# 作者：晨星
"""helios CLI：端到端命令入口（ARG §3 / T11）。"""

from __future__ import annotations

import argparse
import sys

from pathlib import Path

from ..core.config import ProfileConfig
from ..pipeline import Pipeline


def _build_pipeline(profile: str) -> Pipeline:
    cfg = ProfileConfig.from_env({"HELIOS_PROFILE": profile})
    return Pipeline(cfg)


def _load_corpus(path: str) -> list[tuple[str, str]]:
    p = Path(path)
    items: list[tuple[str, str]] = []
    files = [p] if p.is_file() else sorted(p.rglob("*.md")) + sorted(p.rglob("*.txt"))
    for f in files:
        text = f.read_text(encoding="utf-8")
        items.append((text, str(f)))
    return items


def cmd_ingest(args: argparse.Namespace) -> int:
    pipe = _build_pipeline(args.profile)
    items = _load_corpus(args.path)
    added = pipe.add_documents(items)
    print(f"[ingest] 摄入 {added} 篇（去重后），共 {pipe.chunk_count} 块")
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    pipe = _build_pipeline(args.profile)
    if args.corpus:
        pipe.add_documents(_load_corpus(args.corpus))
    ans = pipe.query(args.question, top_k=args.top_k)
    print(f"Q: {ans.query}")
    print(f"A: {ans.text}")
    for c in ans.citations:
        print(f"  [{c.citation_id}] {c.doc_id} @ {c.span_start}:{c.span_end} {c.quote[:40]!r}")
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    from ..evalkit.evaluator import run_baselines

    cfg = ProfileConfig.from_env({"HELIOS_PROFILE": args.profile})
    reports = run_baselines(args.corpus, args.gold, cfg)
    header = f"{'baseline':<18}{'doc_hit':>9}{'doc_mrr':>9}{'recall@5':>10}{'ndcg@10':>10}{'p50_ms':>9}"
    print(header)
    for name, rep in reports:
        print(
            f"{name:<18}{rep.doc_hit_rate:>9.3f}{rep.doc_mrr:>9.3f}{rep.recall_at_5:>10.3f}{rep.ndcg_at_10:>10.3f}{rep.latency_p50_ms:>9.1f}"
        )
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from ..api import run_server

    run_server(profile=args.profile, host=args.host, port=args.port)
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    pipe = _build_pipeline(args.profile)
    corpus = [
        ("RAG（检索增强生成）通过在生成前检索外部知识来降低幻觉。", "rag.md"),
        ("FAISS 是高效的稠密向量检索库，支持 IVF 与 HNSW 等索引。", "faiss.md"),
        ("BM25 是经典的词法检索算法，基于词频与逆文档频率。", "bm25.md"),
    ]
    pipe.add_documents(corpus)
    ans = pipe.query(args.question, top_k=args.top_k)
    print(ans.text)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="helios", description="helios-ai-stack RAG CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("ingest", help="摄入语料目录/文件")
    p.add_argument("path")
    p.add_argument("--profile", default="offline")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("query", help="单次问答")
    p.add_argument("question")
    p.add_argument("--corpus", default=None)
    p.add_argument("--profile", default="offline")
    p.add_argument("--top-k", type=int, default=None, dest="top_k")
    p.set_defaults(func=cmd_query)

    p = sub.add_parser("eval", help="跑评测基线")
    p.add_argument("--corpus", default="data/corpus")
    p.add_argument("--gold", default="data/gold/gold.json")
    p.add_argument("--profile", default="offline")
    p.set_defaults(func=cmd_eval)

    p = sub.add_parser("serve", help="启动 HTTP 服务")
    p.add_argument("--profile", default="offline")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("demo", help="内置最小 demo")
    p.add_argument("question", nargs="?", default="什么是 RAG 检索增强生成？")
    p.add_argument("--profile", default="offline")
    p.add_argument("--top-k", type=int, default=None, dest="top_k")
    p.set_defaults(func=cmd_demo)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
