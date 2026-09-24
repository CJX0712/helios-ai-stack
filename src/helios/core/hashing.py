# 作者：晨星
"""确定性哈希工具：blake2b 内容哈希、mmh3 有符号词哈希、稳定 ID（ARCH §4 / T02）。

硬约束：
    * 同输入两次输出必须**逐位相等**（mmh3 无随机种子，blake2b 无盐）；
    * 中文必须走字符 bigram，不能按空格切词（中文没有空格）；
    * 哈希向量 L2 范数 = 1.0 ± 1e-6（float32 精度内）。
"""

from __future__ import annotations

import hashlib
import json

from collections.abc import Sequence

import mmh3
import numpy as np

from .text import hashing_tokens, normalize_text


#: 默认内容哈希字节数（16 字节 = 128 bit，ARCH §8.1 content_hash）。
DEFAULT_HASH_BYTES: int = 16

#: 默认 doc_id 截取长度（十六进制字符数）。
DOC_ID_HEX_LEN: int = 16

#: 符号哈希用的种子偏移（避免与下标哈希碰撞）。
SIGN_SEED_OFFSET: int = 0x9E3779B9


def blake2b_digest(payload: bytes | str, size: int = DEFAULT_HASH_BYTES) -> str:
    """计算 blake2b 十六进制摘要；str 输入按 UTF-8 编码。"""
    data = payload.encode("utf-8") if isinstance(payload, str) else payload
    return hashlib.blake2b(data, digest_size=size).hexdigest()


def content_hash(text: str, size: int = DEFAULT_HASH_BYTES) -> str:
    """归一化文本的 blake2b 内容哈希（幂等去重依据，ARCH §3.1）。"""
    return blake2b_digest(normalize_text(text), size=size)


def doc_id_for(text: str, source: str = "") -> str:
    """由文本（与可选来源路径）派生稳定 doc_id。"""
    payload = normalize_text(text)
    if source:
        payload = f"{payload}|{source}"
    return blake2b_digest(payload)[:DOC_ID_HEX_LEN]


def chunk_id_for(doc_id: str, ordinal: int) -> str:
    """按 ``f"{doc_id}#{ordinal:04d}"`` 生成 chunk_id。"""
    return f"{doc_id}#{ordinal:04d}"


def stable_key(*parts: object, **fields: object) -> str:
    """由多个片段拼出稳定键（用于缓存 key、索引命名空间等），JSON 序列化后哈希。"""
    payload = json.dumps(
        {"parts": [str(part) for part in parts], "fields": {key: str(value) for key, value in sorted(fields.items())}},
        sort_keys=True,
        ensure_ascii=False,
    )
    return blake2b_digest(payload)


def signed_hash(token: str, seed: int = 0) -> int:
    """mmh3 有符号 32 位哈希（确定性，跨进程一致）。"""
    return int(mmh3.hash(token, seed))


def token_slot(token: str, dim: int, seed: int = 0) -> tuple[int, int]:
    """返回 token 在哈希向量中的 ``(下标, 符号)``，符号取 1 或 -1。"""
    index = signed_hash(token, seed) % dim
    sign = 1 if (signed_hash(token, seed + SIGN_SEED_OFFSET) & 1) else -1
    return int(index), int(sign)


def l2_normalize(vector: np.ndarray) -> np.ndarray:
    """L2 归一化；零向量原样返回，避免除零。

    归一化在 float64 下计算后再落回 float32，保证范数误差远小于 1e-6。
    """
    array = np.asarray(vector, dtype=np.float64)
    norm = float(np.linalg.norm(array))
    if norm <= 0.0 or not np.isfinite(norm):
        return np.zeros_like(array, dtype=np.float32)
    return (array / norm).astype(np.float32)


def hash_vector(
    tokens: Sequence[str],
    dim: int,
    seed: int = 0,
    weights: Sequence[float] | None = None,
) -> np.ndarray:
    """有符号哈希技巧（signed hashing trick）把 token 序列压成定维 L2 归一向量。

    Args:
        tokens: token 序列（中文应传入字符 bigram）。
        dim: 目标维度。
        seed: 哈希种子，用于构造多视图。
        weights: 可选 token 权重（如 TF / IDF），长度需与 tokens 一致。

    Returns:
        ``shape=(dim,)`` 的 float32 向量，L2 范数为 1.0（零输入时为全零）。
    """
    if dim <= 0:
        raise ValueError("dim 必须为正整数")
    accumulator = np.zeros(dim, dtype=np.float64)
    for position, token in enumerate(tokens):
        weight = 1.0 if weights is None else float(weights[position])
        index, sign = token_slot(token, dim, seed)
        accumulator[index] += sign * weight
    return l2_normalize(accumulator)


def hash_text_vector(text: str, dim: int, seed: int = 0) -> np.ndarray:
    """文本直出哈希向量：拉丁词 + 中文字符 bigram，同输入逐位相等。"""
    return hash_vector(hashing_tokens(text), dim=dim, seed=seed)


def hash_text_matrix(texts: Sequence[str], dim: int, seed: int = 0) -> np.ndarray:
    """批量文本哈希，返回 ``shape=(len(texts), dim)`` 的 float32 矩阵。"""
    matrix = np.zeros((len(texts), dim), dtype=np.float32)
    for row, text in enumerate(texts):
        matrix[row] = hash_text_vector(text, dim=dim, seed=seed)
    return matrix
