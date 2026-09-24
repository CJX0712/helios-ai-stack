# 作者：晨星
"""OpenAI 兼容远端生成（remote 档默认；需 API Key，ARCH §7 / T09）。"""

from __future__ import annotations

import os

from collections.abc import Iterator
from typing import Any

from ..core.net import build_client, guard


class OpenAICompatLLM:
    """OpenAI 兼容 Chat Completions 生成器；满足 LLM Protocol。"""

    def __init__(self, config: Any | None = None) -> None:
        self.model: str = getattr(config, "llm_model", None) or "gpt-4o-mini"
        self._base: str = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self._key: str = os.environ.get("OPENAI_API_KEY", "")

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._key:
            headers["Authorization"] = f"Bearer {self._key}"
        return headers

    def generate(self, prompt: str) -> str:
        """一次性生成完整回答。"""
        guard(f"{self._base}/chat/completions", component="llm")
        with build_client(base_url=self._base, timeout_s=120.0) as client:
            resp = client.post(
                "/chat/completions",
                headers=self._headers(),
                json={"model": self.model, "messages": [{"role": "user", "content": prompt}], "stream": False},
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()

    def stream(self, prompt: str) -> Iterator[str]:
        """流式生成（SSE），逐段产出文本。"""
        guard(f"{self._base}/chat/completions", component="llm")
        with build_client(base_url=self._base, timeout_s=120.0) as client, client.stream(
            "POST",
            "/chat/completions",
            headers=self._headers(),
            json={"model": self.model, "messages": [{"role": "user", "content": prompt}], "stream": True},
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                payload = line[len("data:") :].strip()
                if payload == "[DONE]":
                    break
                try:
                    chunk = __import__("json").loads(payload)
                except __import__("json").JSONDecodeError:
                    continue
                delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
                if delta:
                    yield delta

    def diagnostics(self) -> dict[str, Any]:
        """后端自检；``_error`` 为 ``None`` 表示可用。"""
        if not self._key:
            return {"backend": "openai", "model": self.model, "_error": "未配置 OPENAI_API_KEY", "base": self._base}
        return {"backend": "openai", "model": self.model, "base": self._base, "_error": None}
