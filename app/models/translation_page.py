from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class TranslationBlockView:
    page_number: int
    block_index: int
    block_type: str
    source_text: str
    translated_text: str
    title: str = ""
    extra: dict = field(default_factory=dict)


@dataclass(slots=True)
class TranslationPageView:
    page_number: int
    blocks: list[TranslationBlockView]
    heading: str = ""
    meta: str = ""

