# 作者：晨星
"""llama.cpp 本地 GGUF 生成（可选增强；缺库/权重则回落，ARCH §7 / T09）。"""

from __future__ import annotations

import os

from collections.abc import Iterator
from typing import Any

from ..core import codes
from ..core.errors import raise_for


class LlamaCppLLM:
    """llama.cpp GGUF 本地生成器；满足 LLM Protocol。"""

    def __init__(self, config: Any | None = None) -> None:
        self.model: str = getattr(config, "llm_model", None) or "qwen2.5-7b-instruct-q4_K_M.gguf"
        self._model_dir: str = os.environ.get("HELIOS_MODEL_DIR", getattr(config, "model_dir", "models/"))
        self._ctx: int = int(getattr(config, "llm_ctx", None) or 4096)
        self._threads: int = int(getattr(config, "llm_threads", None) or 4)
        self._llm = None

    def _ensure(self) -> None:
        if self._llm is not None:
            return
        try:
            from llama_cpp import Llama
        except ImportError as exc:  # pragma: no cover - 可选依赖缺失
            raise raise_for(codes.E_LLM_MODEL_MISSING, message="llama_cpp 不可用", detail={"error": str(exc)}) from exc
        path = os.path.join(self._model_dir, self.model)
        if not os.path.isfile(path):
            raise raise_for(codes.E_LLM_MODEL_MISSING, message="GGUF 权重缺失", detail={"path": path})
        self._llm = Llama(model_path=path, n_ctx=self._ctx, n_threads=self._threads, verbose=False)

    def generate(self, prompt: str) -> str:
        """一次性生成完整回答。"""
        self._ensure()
        assert self._llm is not None
        out = self._llm(prompt, max_tokens=512, temperature=0.1)
        return out["choices"][0]["text"].strip()

    def stream(self, prompt: str) -> Iterator[str]:
        """流式生成，逐段产出文本。"""
        self._ensure()
        assert self._llm is not None
        for chunk in self._llm(prompt, max_tokens=512, temperature=0.1, stream=True):
            text = chunk["choices"][0]["text"]
            if text:
                yield text

    def diagnostics(self) -> dict[str, Any]:
        """后端自检；``_error`` 为 ``None`` 表示可用。"""
        try:
            self._ensure()
        except Exception as exc:  # pragma: no cover - 依赖/权重缺失分支
            return {"backend": "llama_cpp", "model": self.model, "_error": str(exc)}
        return {"backend": "llama_cpp", "model": self.model, "_error": None}
