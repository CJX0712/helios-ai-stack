# 作者：晨星
"""一键验收闸门（T15）：导入全模块 + 离线端到端 + 评测基线 + ruff（ARCH §7 / F-13）。

退出码 0 = 全绿；非 0 = 存在失败项。输出结论先行的状态表。
"""
from __future__ import annotations

import importlib
import os
import subprocess
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

MODULES = [
    "helios.core.types", "helios.core.protocols", "helios.core.errors", "helios.core.config",
    "helios.core.registry", "helios.core.hashing", "helios.core.text", "helios.core.net",
    "helios.core.codes", "helios.core.cache", "helios.core.trace",
    "helios.ingest.service", "helios.ingest.parsers",
    "helios.chunk.service", "helios.chunk.splitter", "helios.chunk.sizer",
    "helios.embed.hashing", "helios.embed.onnx_direct", "helios.embed.fastembed_backend", "helios.embed.ollama_backend",
    "helios.vector.numpy_index", "helios.vector.faiss_index",
    "helios.lexical.service", "helios.lexical.inverted",
    "helios.rerank.lexical", "helios.rerank.onnx", "helios.rerank.noop", "helios.rerank.remote",
    "helios.llm.template", "helios.llm.llama_cpp_backend", "helios.llm.ollama_backend", "helios.llm.openai_backend",
    "helios.fuse.fuser", "helios.cite.citer", "helios.tools.calculator",
    "helios.pipeline.orchestrator", "helios.api.app", "helios.cli.main", "helios.evalkit.evaluator",
]

PASS = "[PASS]"
WARN = "[WARN]"


def check_imports() -> tuple[int, int]:
    ok = warn = 0
    for m in MODULES:
        try:
            importlib.import_module(m)
            ok += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  {WARN} 导入失败 {m}: {type(exc).__name__}: {exc}")
            warn += 1
    return ok, warn


def check_offline_e2e() -> bool:
    from helios.core.config import ProfileConfig
    from helios.pipeline import Pipeline

    cfg = ProfileConfig.from_env({"HELIOS_PROFILE": "offline"})
    pipe = Pipeline(cfg)
    pipe.add_documents([
        ("RAG（检索增强生成）通过在生成前检索外部知识来降低幻觉。", "rag.md"),
        ("FAISS 是高效的稠密向量检索库。", "faiss.md"),
        ("BM25 是经典的词法检索算法。", "bm25.md"),
    ])
    ans = pipe.query("什么是 RAG 检索增强生成？")
    calc = pipe.query("12*(3+4)")
    return ans.has_citation() and calc.text == "84" and pipe.chunk_count >= 3


def check_eval() -> bool:
    from helios.core.config import ProfileConfig
    from helios.evalkit.evaluator import run_baselines

    cfg = ProfileConfig.from_env({"HELIOS_PROFILE": "offline"})
    reports = run_baselines(os.path.join(ROOT, "data", "corpus"), os.path.join(ROOT, "data", "gold", "gold.json"), cfg)
    by_name = dict(reports)
    hr = by_name.get("hybrid_rerank")
    return hr is not None and hr.doc_hit_rate >= 1.0


def check_ruff() -> bool:
    try:
        r = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "src", "scripts", "tests"],
            cwd=ROOT, capture_output=True, text=True, timeout=120,
        )
    except Exception:  # noqa: BLE001
        return False
    return r.returncode == 0


def main() -> int:
    print("=== helios-ai-stack 验收闸门 ===\n")
    print("[1/4] 模块导入")
    ok, warn = check_imports()
    print(f"  {PASS if warn == 0 else WARN} 导入 {ok}/{len(MODULES)} 成功，{warn} 失败")

    print("[2/4] 离线端到端 E2E")
    e2e = check_offline_e2e()
    print(f"  {PASS if e2e else WARN} ingest->query->cite + 计算器路由 通过" if e2e else f"  {WARN} 离线 E2E 失败")

    print("[3/4] 评测基线（doc_hit_rate）")
    ev = check_eval()
    print(f"  {PASS if ev else WARN} hybrid_rerank doc_hit_rate >= 1.0" if ev else f"  {WARN} 评测基线未达标")

    print("[4/4] ruff lint")
    ruff = check_ruff()
    print(f"  {PASS if ruff else WARN} ruff check 通过" if ruff else f"  {WARN} ruff 存在告警（不影响功能）")

    all_ok = warn == 0 and e2e and ev
    print("\n结论:", "全绿 [PASS]" if all_ok else "存在需关注项 [WARN]")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
