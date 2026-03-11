from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Note:
    id: int | None = None
    paper_id: int = 0
    page_number: int = 0
    selected_text: str = ""
    note_content: str = ""

