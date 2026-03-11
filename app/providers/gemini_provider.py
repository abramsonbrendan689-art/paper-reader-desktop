from __future__ import annotations

from typing import Any

import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.exceptions import ProviderUnavailableError
from app.prompts.templates import (
    ACADEMIC_TRANSLATION_PROMPT,
    PARAGRAPH_EXPLAIN_PROMPT,
    SUMMARY_PROMPT,
)
from app.providers.base_provider import BaseProvider


class GeminiProvider(BaseProvider):
    name = "gemini"

    def __init__(self, api_key: str, model_name: str = "gemini-1.5-flash"):
        self.api_key = api_key
        self.model_name = model_name or "gemini-1.5-flash"
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(self.model_name)
        else:
            self.model = None

    def is_configured(self) -> bool:
        return bool(self.api_key and self.model)

    def availability_reason(self) -> str:
        if self.is_configured():
            return ""
        return "Gemini API Key 未配置"

    @retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3))
    def _generate(self, prompt: str) -> str:
        if not self.model:
            raise ProviderUnavailableError("Gemini API Key 未配置")
        resp = self.model.generate_content(prompt)
        text = getattr(resp, "text", "") or ""
        return text.strip()

    def translate(
        self,
        text: str,
        source_lang: str = "en",
        target_lang: str = "zh",
        options: dict[str, Any] | None = None,
    ) -> str:
        opts = options or {}
        glossary = opts.get("glossary", "none")
        prompt = (
            f"{ACADEMIC_TRANSLATION_PROMPT.format(glossary=glossary)}\n\n"
            f"Source language: {source_lang}\nTarget language: {target_lang}\n\n{text}"
        )
        return self._generate(prompt)

    def summarize(self, text: str, options: dict[str, Any] | None = None) -> str:
        return self._generate(f"{SUMMARY_PROMPT}\n\n{text}")

    def explain(
        self,
        text: str,
        question: str,
        options: dict[str, Any] | None = None,
    ) -> str:
        prompt = f"{PARAGRAPH_EXPLAIN_PROMPT}\n\nQuestion: {question}\n\nParagraph:\n{text}"
        return self._generate(prompt)
