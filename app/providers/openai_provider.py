from __future__ import annotations

from typing import Any

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.exceptions import ProviderUnavailableError
from app.prompts.templates import (
    ACADEMIC_TRANSLATION_PROMPT,
    PARAGRAPH_EXPLAIN_PROMPT,
    SUMMARY_PROMPT,
)
from app.providers.base_provider import BaseProvider


class OpenAIProvider(BaseProvider):
    name = "openai"

    def __init__(self, api_key: str, model_name: str, timeout: int = 60):
        self.api_key = api_key
        self.model_name = model_name or "gpt-4.1-mini"
        self.timeout = timeout
        self.client = OpenAI(api_key=api_key, timeout=timeout) if api_key else None

    def is_configured(self) -> bool:
        return bool(self.api_key and self.client)

    def availability_reason(self) -> str:
        if self.is_configured():
            return ""
        return "OpenAI API Key 未配置"

    @retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3))
    def _chat(self, system_prompt: str, user_text: str, options: dict[str, Any] | None = None) -> str:
        if not self.client:
            raise ProviderUnavailableError("OpenAI API Key 未配置")

        opts = options or {}
        response = self.client.chat.completions.create(
            model=opts.get("model_name", self.model_name),
            temperature=float(opts.get("temperature", 0.1)),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
        )
        content = response.choices[0].message.content if response.choices else ""
        return (content or "").strip()

    def translate(
        self,
        text: str,
        source_lang: str = "en",
        target_lang: str = "zh",
        options: dict[str, Any] | None = None,
    ) -> str:
        opts = options or {}
        glossary = opts.get("glossary", "none")
        system_prompt = ACADEMIC_TRANSLATION_PROMPT.format(glossary=glossary)
        user_text = f"Source language: {source_lang}\nTarget language: {target_lang}\n\n{text}"
        return self._chat(system_prompt, user_text, opts)

    def summarize(self, text: str, options: dict[str, Any] | None = None) -> str:
        return self._chat(SUMMARY_PROMPT, text, options)

    def explain(
        self,
        text: str,
        question: str,
        options: dict[str, Any] | None = None,
    ) -> str:
        user_text = f"{PARAGRAPH_EXPLAIN_PROMPT}\n\nQuestion: {question}\n\nParagraph:\n{text}"
        return self._chat(PARAGRAPH_EXPLAIN_PROMPT, user_text, options)
