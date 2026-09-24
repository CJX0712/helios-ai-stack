# 作者：晨星
"""Ollama 生成后端：调用本机 /api/generate（local 档默认，零下载，ARCH §7 / T09）。"""

from __future__ import annotations

import json

from collections.abc import Iterator
from typing import Any

from ..core import codes
from ..core.errors import raise_for
from ..core.net import build_client, ollama_host


class OllamaLLM:
    """Ollama 文本生成器；满足 LLM Protocol。"""

    def __init__(self, config: Any | None = None) -> None:
        self.model: str = getattr(config, "llm_model", None) or "qwen2.5:7b-instruct-q4_K_M"
        self._host = ollama_host()
        self._ctx: int = int(getattr(config, "llm_ctx", None) or 4096)
        self._threads: int = int(getattr(config, "llm_threads", None) or 4)

    def _payload(self, prompt: str, stream: bool) -> dict[str, Any]:
        return {
            "model": self.model,
            "prompt": prompt,
            "stream": stream,
            "options": {"num_ctx": self._ctx, "num_thread": self._threads},
        }

    def generate(self, prompt: str) -> str:
        """一次性生成完整回答。"""
        import httpx

        try:
            with build_client(base_url=self._host, timeout_s=120.0) as client:
                resp = client.post("/api/generate", json=self._payload(prompt, False))
                resp.raise_for_status()
                return resp.json().get("response", "").strip()
        except httpx.HTTPError as exc:
            raise raise_for(
                codes.E_LLM_MODEL_MISSING,
                message="Ollama 生成不可用",
                detail={"model": self.model, "error": str(exc)},
            ) from exc

    def stream(self, prompt: str) -> Iterator[str]:
        """流式生成，逐段产出文本。"""
        import httpx

        try:
            with (
                build_client(base_url=self._host, timeout_s=120.0) as client,
                client.stream("POST", "/api/generate", json=self._payload(prompt, True)) as resp,
            ):
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    if chunk.get("response"):
                        yield chunk["response"]
        except httpx.HTTPError as exc:
            raise raise_for(
                codes.E_LLM_MODEL_MISSING,
                message="Ollama 流式生成不可用",
                detail={"model": self.model, "error": str(exc)},
            ) from exc

    def diagnostics(self) -> dict[str, Any]:
        """后端自检；``_error`` 为 ``None`` 表示可用。"""
        import httpx

        try:
            with build_client(base_url=self._host, timeout_s=5.0) as client:
                resp = client.get("/api/tags")
                ok = resp.status_code == 200
                models = [m.get("name", "") for m in resp.json().get("models", [])] if ok else []
        except httpx.HTTPError as exc:
            return {"backend": "ollama", "model": self.model, "_error": str(exc), "available_models": []}
        err = None if ok else "ollama 未就绪"
        if ok and self.model not in models:
            err = f"模型 {self.model} 未安装"
        return {"backend": "ollama", "model": self.model, "_error": err, "available_models": models}
