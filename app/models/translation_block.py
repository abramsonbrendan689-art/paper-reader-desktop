from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TranslationBlock:
    paper_id: int
    page_number: int
    block_index: int
    source_text: str
    translated_text: str
    provider_name: str
    source_lang: str = "en"
    target_lang: str = "zh"
    checksum: str = ""

