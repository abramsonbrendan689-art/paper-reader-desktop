from __future__ import annotations

import re
import shutil
from pathlib import Path


def sanitize_filename(name: str) -> str:
    safe = re.sub(r'[\\\\/:*?"<>|]', "_", name)
    safe = re.sub(r"\s+", " ", safe).strip()
    return safe or "untitled"


def unique_path(target_dir: Path, preferred_name: str, suffix: str) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    base = sanitize_filename(preferred_name)
    candidate = target_dir / f"{base}{suffix}"
    index = 1
    while candidate.exists():
        candidate = target_dir / f"{base}_{index}{suffix}"
        index += 1
    return candidate


def safe_copy(src: str | Path, target_dir: Path, preferred_name: str) -> Path:
    src_path = Path(src)
    dst_path = unique_path(target_dir, preferred_name, src_path.suffix.lower())
    shutil.copy2(src_path, dst_path)
    return dst_path

