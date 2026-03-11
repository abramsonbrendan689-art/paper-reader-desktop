from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CitationResult:
    style_name: str
    citation_text: str
    bibtex_text: str = ""

