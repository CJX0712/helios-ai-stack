# 作者：晨星
"""核心契约测试：哈希确定性、配置加载、错误码不变量、HTTP 映射。"""
from __future__ import annotations

from helios.core import codes
from helios.core.config import ProfileConfig
from helios.core.errors import BadInputError, HeliosError, raise_for
from helios.core.hashing import content_hash, doc_id_for, hash_text_vector
from helios.core.text import lexical_tokens, normalize_text, split_sentences


def test_hashing_deterministic():
    a = content_hash("RAG 检索增强生成")
    b = content_hash("RAG 检索增强生成")
    assert a == b
    assert doc_id_for("相同文本", "src") == doc_id_for("相同文本", "src")


def test_hash_vector_l2_norm():
    import numpy as np

    v = hash_text_vector("向量检索 cosine", 256)
    assert abs(float(np.linalg.norm(v)) - 1.0) < 1e-5


def test_normalize_folds_whitespace_and_fullwidth():
    out = normalize_text("Python　3.10   发布了")
    assert "　" not in out
    assert "  " not in out


def test_split_sentences_keeps_version_number():
    parts = split_sentences("Python 3.10 发布了。它很快。")
    assert len(parts) == 2
    assert "Python 3.10 发布了。" in parts


def test_lexical_tokens_chinese_bigram():
    toks = lexical_tokens("嵌入模型")
    assert "嵌入" in toks and "入模" in toks and "模型" in toks


def test_config_offline_loads():
    cfg = ProfileConfig.from_env({"HELIOS_PROFILE": "offline"})
    assert cfg.profile == "offline"
    assert cfg.embed_backend == "hashing"
    assert cfg.vector_backend == "numpy"
    assert cfg.lexical_backend == "bm25"
    assert cfg.rerank_backend == "lexical"
    assert cfg.llm_backend == "template"


def test_config_env_override():
    cfg = ProfileConfig.from_env({"HELIOS_PROFILE": "offline", "HELIOS_TOP_K": "9"})
    assert cfg.top_k == 9


def test_all_codes_match_pattern_and_http_status():
    for code in codes.ALL_CODES:
        assert codes.CODE_PATTERN.match(code), code
        assert code in codes.HTTP_STATUS, code
        assert 100 <= codes.http_status(code) <= 599


def test_helios_error_to_http():
    err = BadInputError(message="坏输入", detail={"field": "x"})
    status, body = err.to_http()
    assert status == 400
    assert body["error"]["code"] == codes.E_CORE_BAD_INPUT
    assert body["error"]["detail"]["field"] == "x"


def test_raise_for_returns_error():
    err = raise_for(codes.E_CORE_NOT_FOUND, message="找不到")
    assert isinstance(err, HeliosError)
    assert err.code == codes.E_CORE_NOT_FOUND
