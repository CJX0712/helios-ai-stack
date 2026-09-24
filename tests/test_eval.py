# 作者：晨星
"""评测基线测试：四组基线可跑，hybrid_rerank 文档命中率 100%，指标落在 [0,1]。"""
from __future__ import annotations

from pathlib import Path

import pytest

from helios.core.config import ProfileConfig
from helios.evalkit.evaluator import run_baselines


ROOT = Path(__file__).resolve().parents[1]
CORPUS = str(ROOT / "data" / "corpus")
GOLD = str(ROOT / "data" / "gold" / "gold.json")


@pytest.mark.skipif(not Path(CORPUS).is_dir(), reason="语料缺失")
def test_baselines_doc_hit_rate():
    cfg = ProfileConfig.from_env({"HELIOS_PROFILE": "offline"})
    reports = run_baselines(CORPUS, GOLD, cfg)
    assert reports, "基线为空"
    by_name = dict(reports)
    assert "hybrid_rerank" in by_name
    for _name, rep in reports:
        assert 0.0 <= rep.doc_hit_rate <= 1.0
        assert 0.0 <= rep.doc_mrr <= 1.0
        assert 0.0 <= rep.ndcg_at_10 <= 1.0
        assert rep.query_count > 0
    # 离线小语料上 hybrid+rerank 应达到文档命中率 100%
    assert by_name["hybrid_rerank"].doc_hit_rate == 1.0
