# 作者：晨星
"""生成精确版本锁（T15）：扫描当前环境已装版本，回填 requirements.lock.txt。

说明：版本钉死来自本机实测安装；sha256 需经 pip download 扫描 wheel 后补齐，
在补齐前 install.py 会以不带 --require-hashes 的方式安装。
"""
from __future__ import annotations

import importlib.metadata as md
import os


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PACKAGES = [
    "numpy", "pydantic", "PyYAML", "mmh3", "diskcache", "loguru", "httpx", "rank-bm25",
    "pypdf", "fastapi", "uvicorn", "starlette", "faiss-cpu", "onnxruntime", "tokenizers",
    "fastembed", "llama-cpp-python", "mcp", "pytest", "ruff",
]


def main() -> int:
    lines = [
        "# 作者：晨星",
        "# helios-ai-stack 精确版本锁（由 scripts/gen_lock.py 扫描本机环境生成）。",
        "# 纪律：无 GPL / AGPL / LGPL 传染性依赖（ARCH §7.1）。",
        "",
    ]
    missing = []
    for pkg in PACKAGES:
        try:
            version = md.version(pkg)
            lines.append(f"{pkg}=={version}")
        except md.PackageNotFoundError:
            missing.append(pkg)
    if missing:
        lines.append("")
        lines.append(f"# 以下依赖本机未安装（可选或按需）：{', '.join(missing)}")
    out = os.path.join(ROOT, "requirements.lock.txt")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"[gen_lock] 已写入 {out}（{len(PACKAGES) - len(missing)}/{len(PACKAGES)} 个已锁版本）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
