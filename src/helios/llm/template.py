# 作者：晨星
"""确定性模板生成器：抽取式答案 + 计算器路由（offline 默认 LLM，ARCH §7 / T09）。

不调用任何外部模型；从 prompt 中的 CONTEXT 区块抽取与 QUESTION 词法重叠最高的句子组成答案，
纯算术问题则经 Calculator 直出，保证 offline 可复现且答案有出处。
"""

from __future__ import annotations

import re

from collections.abc import Iterator
from typing import Any

from ..core.text import lexical_tokens, split_sentences
from ..tools.calculator import Calculator


_QUESTION_RE = re.compile(r"QUESTION:\s*(.*?)\s*(?:ANSWER:|$)", re.DOTALL)
_CONTEXT_RE = re.compile(r"CONTEXT:\s*(.*?)\s*QUESTION:", re.DOTALL)
_ENTRY_RE = re.compile(r"\[\d+\]\s*(.*?)(?=\n\[\d+\]|\Z)", re.DOTALL)


def build_prompt(question: str, chunks: list, max_context_chars: int = 2000) -> str:
    """构造模板 LLM 消费的 prompt：CONTEXT 区块 + QUESTION。"""
    blocks: list[str] = []
    budget = max_context_chars
    for index, ch in enumerate(chunks, start=1):
        text = ch.text if hasattr(ch, "text") else str(ch)
        if len(text) > budget + 200:
            text = text[: budget + 200]
        blocks.append(f"[{index}] {text}")
        budget -= len(text)
        if budget <= 0:
            break
    context = "\n".join(blocks)
    return (
        "You are a retrieval-augmented assistant. Use only the CONTEXT to answer.\n\n"
        f"CONTEXT:\n{context}\n\n"
        f"QUESTION: {question}\n\n"
        "ANSWER:"
    )


class TemplateLLM:
    """确定性抽取式 LLM；满足 LLM Protocol。"""

    def __init__(self, config: Any | None = None) -> None:
        self._calculator = Calculator(config)
        self._name = "template"

    def generate(self, prompt: str) -> str:
        """一次性生成完整回答。"""
        question = self._extract_question(prompt)
        if self._calculator.can_handle(question):
            return self._calculator.run(question)
        context = self._extract_context(prompt)
        if not context:
            return question if question else ""
        q_tokens = set(lexical_tokens(question))
        picked: list[str] = []
        seen: set[str] = set()
        for entry in context:
            sentences = split_sentences(entry)
            if not sentences:
                continue
            entry_tokens = set(lexical_tokens(entry))
            if q_tokens & entry_tokens:
                for sentence in sentences:
                    key = sentence.strip()
                    if key and key not in seen and (q_tokens & set(lexical_tokens(sentence))):
                        picked.append(key)
                        seen.add(key)
            if len(picked) >= 3:
                break
        if not picked:
            picked = [split_sentences(entry)[0] for entry in context if split_sentences(entry)]
            picked = picked[:2]
        lead = "根据检索内容，" if picked else ""
        return lead + "".join(picked)

    def stream(self, prompt: str) -> Iterator[str]:
        """流式生成，按句产出。"""
        text = self.generate(prompt)
        yield from split_sentences(text) or [text]

    def diagnostics(self) -> dict[str, Any]:
        """后端自检；``_error`` 为 ``None`` 表示可用。"""
        return {"backend": self._name, "_error": None}

    @staticmethod
    def _extract_question(prompt: str) -> str:
        match = _QUESTION_RE.search(prompt)
        return match.group(1).strip() if match else prompt.strip()

    @staticmethod
    def _extract_context(prompt: str) -> list[str]:
        match = _CONTEXT_RE.search(prompt)
        if not match:
            return []
        body = match.group(1)
        entries = _ENTRY_RE.findall(body)
        return [e.strip() for e in entries if e.strip()]
