# 作者：晨星
"""后端注册表与可注入实现测试：16 个后端均可解析，offline 默认后端可用。"""
from __future__ import annotations

import importlib

from helios.core.config import ProfileConfig
from helios.core.registry import DEFAULT_SPECS, build_any, resolve


def _specs():
    specs = []
    for cap, table in DEFAULT_SPECS.items():
        for name, spec in table.items():
            specs.append((cap, name, spec))
    return specs


def test_all_16_backends_importable():
    bad = []
    for cap, name, spec in _specs():
        try:
            mod = importlib.import_module(spec.module)
            getattr(mod, spec.cls)
        except Exception as exc:  # noqa: BLE001
            bad.append((cap, name, str(exc)))
    assert not bad, f"无法导入的后端: {bad}"


def test_offline_backends_resolve_and_diagnostics():
    cfg = ProfileConfig.from_env({"HELIOS_PROFILE": "offline"})
    for cap, name in [("embed", "hashing"), ("vector", "numpy"), ("lexical", "bm25"), ("rerank", "lexical"), ("llm", "template")]:
        inst = resolve(cap, name, cfg)
        diag = inst.diagnostics()
        assert "_error" in diag, f"{cap}/{name} 缺少 _error 键"
        assert diag["_error"] is None, f"{cap}/{name} 自检报错: {diag['_error']}"


def test_fallback_chain_offline():
    cfg = ProfileConfig.from_env({"HELIOS_PROFILE": "offline"})
    # 离线档应直接拿到 hashing 嵌入器
    emb = build_any("embed", cfg)
    assert emb.dim == cfg.embed_dim
