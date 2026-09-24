# 作者：晨星
"""一键 demo（T17）：干净环境零下载跑通端到端 RAG（offline 档）。

用法：python scripts/run_demo.py [--profile offline]
"""
from __future__ import annotations

import argparse
import os
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)


def _ensure_utf8() -> None:
    """强制 stdout/stderr 用 UTF-8，避免非 UTF-8 终端（如 en-US CI 的 cp1252）打印中文时崩溃。"""
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def main() -> int:
    _ensure_utf8()
    parser = argparse.ArgumentParser(description="helios-ai-stack 一键 demo")
    parser.add_argument("--profile", default="offline")
    args = parser.parse_args()

    from helios.core.config import ProfileConfig
    from helios.pipeline import Pipeline

    cfg = ProfileConfig.from_env({"HELIOS_PROFILE": args.profile})
    pipe = Pipeline(cfg)

    corpus_dir = os.path.join(ROOT, "data", "corpus")
    count = 0
    if os.path.isdir(corpus_dir):
        for name in sorted(os.listdir(corpus_dir)):
            if name.endswith((".md", ".txt")):
                path = os.path.join(corpus_dir, name)
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
                if pipe.add_document(text, path):
                    count += 1
    print(f"[demo] 摄入 {count} 篇文档，{pipe.chunk_count} 块，profile={cfg.profile}")

    questions = [
        "什么是 RAG 检索增强生成？",
        "BM25 是怎么打分的？",
        "Faiss 支持哪些索引？",
        "12*(3+4) 等于多少？",
    ]
    for q in questions:
        ans = pipe.query(q)
        print(f"\nQ: {q}")
        print(f"A: {ans.text}")
        print(f"  引用 {len(ans.citations)} 条，耗时 {ans.timings.get('total_ms', 0):.1f}ms")

    print("\n[demo] 端到端跑通 OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
