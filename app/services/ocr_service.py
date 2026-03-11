from __future__ import annotations

from pathlib import Path


class OCRService:
    """
    OCR 扩展接口（MVP 预留）:
    - 后续可对接 PaddleOCR / Tesseract
    - 当前版本聚焦文本型 PDF，不在主流程中调用
    """

    def extract_text(self, file_path: str | Path) -> str:
        raise NotImplementedError("OCRService 尚未实现，请后续接入 PaddleOCR/Tesseract。")

