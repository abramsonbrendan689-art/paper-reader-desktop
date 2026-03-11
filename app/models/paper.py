from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Paper:
    id: int | None = None
    original_filename: str = ""
    display_name_cn: str = ""
    title: str = ""
    title_cn: str = ""
    authors: str = ""
    year: str = ""
    journal: str = ""
    conference: str = ""
    doi: str = ""
    abstract: str = ""
    abstract_cn: str = ""
    keywords: str = ""
    category: str = ""
    tags: str = ""
    file_path: str = ""


@dataclass(slots=True)
class PaperBlock:
    page_number: int
    block_index: int
    text: str
    bbox: tuple[float, float, float, float]
    avg_font_size: float
    span_count: int
    block_type: str = "body"
    extra: dict = field(default_factory=dict)

