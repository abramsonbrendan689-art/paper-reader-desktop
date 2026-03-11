from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AppSettings:
    id: int = 1
    default_provider: str = "deepseek"
    model_name: str = "deepseek-chat"
    use_reasoning_for_analysis: bool = False
    storage_dir: str = "./storage"
    cache_dir: str = "./cache"
    db_path: str = "./data/literature_reader.db"
    ui_theme: str = "light"
