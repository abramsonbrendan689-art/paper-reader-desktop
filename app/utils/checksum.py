from __future__ import annotations

import hashlib
from pathlib import Path


def md5_text(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def md5_file(path: str | Path) -> str:
    file_path = Path(path)
    digest = hashlib.md5()
    with file_path.open("rb") as fp:
        while True:
            chunk = fp.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()

