from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger


def setup_logging(log_dir: Path, level: str = "INFO") -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(
        sys.stderr,
        level=level.upper(),
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | {message}",
    )
    logger.add(
        log_dir / "app.log",
        level=level.upper(),
        rotation="5 MB",
        retention=5,
        encoding="utf-8",
    )


__all__ = ["logger", "setup_logging"]

