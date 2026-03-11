from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ReadingState:
    id: int | None = None
    paper_id: int = 0
    last_page: int = 0
    scroll_ratio: float = 0.0
