from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseProvider(ABC):
    name: str = "base"

    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError

    def availability_reason(self) -> str:
        return ""

    @abstractmethod
    def translate(
        self,
        text: str,
        source_lang: str = "en",
        target_lang: str = "zh",
        options: dict[str, Any] | None = None,
    ) -> str:
        raise NotImplementedError

    def translate_blocks(
        self,
        blocks: list[dict[str, Any]],
        source_lang: str = "en",
        target_lang: str = "zh",
        options: dict[str, Any] | None = None,
    ) -> list[str]:
        translated: list[str] = []
        for item in blocks:
            text = (item.get("text") if isinstance(item, dict) else str(item)) or ""
            translated.append(
                self.translate(
                    text=text,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    options=options,
                )
            )
        return translated

    @abstractmethod
    def summarize(self, text: str, options: dict[str, Any] | None = None) -> str:
        raise NotImplementedError

    @abstractmethod
    def explain(
        self,
        text: str,
        question: str,
        options: dict[str, Any] | None = None,
    ) -> str:
        raise NotImplementedError

    @abstractmethod
    def analyze_paper(self, text: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        raise NotImplementedError

    def chat(self, messages: list[dict[str, str]], options: dict[str, Any] | None = None) -> str:
        raise NotImplementedError

    def get_model_name(self, reasoning: bool = False) -> str:
        return ""

    @abstractmethod
    def test_connection(self) -> tuple[bool, str]:
        raise NotImplementedError
