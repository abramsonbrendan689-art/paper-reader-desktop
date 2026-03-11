from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ChatMessage:
    id: int | None = None
    paper_id: int = 0
    role: str = "user"
    content: str = ""
