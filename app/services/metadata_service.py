from __future__ import annotations

import re
from pathlib import Path

from app.services.pdf_service import PDFService
from app.utils.text_utils import extract_year, normalize_whitespace


class MetadataService:
    DOI_PATTERN = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)

    def __init__(self, pdf_service: PDFService):
        self.pdf_service = pdf_service

    def extract_metadata(self, pdf_path: str | Path) -> dict[str, str]:
        first_page_blocks = self.pdf_service.extract_page_blocks(pdf_path, 0)
        sample_text = self.pdf_service.extract_document_text(pdf_path, max_pages=2)

        title = self._guess_title(first_page_blocks)
        authors = self._guess_authors(first_page_blocks, title)
        year = extract_year(sample_text)
        doi = self._extract_doi(sample_text)
        abstract = self._extract_section(sample_text, "abstract", ("keywords", "introduction", "1."))
        keywords = self._extract_section(sample_text, "keywords", ("introduction", "1.", "index terms"))

        return {
            "title": title,
            "authors": authors,
            "year": year,
            "doi": doi,
            "journal": "",
            "conference": "",
            "abstract": abstract,
            "keywords": keywords,
        }

    def _guess_title(self, blocks: list) -> str:
        if not blocks:
            return ""
        candidates = [b for b in blocks if b.block_type in {"heading", "body"} and len(b.text) > 8]
        if not candidates:
            return blocks[0].text[:200]
        candidates.sort(key=lambda x: (x.avg_font_size, -x.bbox[1]), reverse=True)
        return normalize_whitespace(candidates[0].text[:300])

    def _guess_authors(self, blocks: list, title: str) -> str:
        if not blocks:
            return ""
        title_found = False
        for block in blocks:
            if not title_found and title and title in block.text:
                title_found = True
                continue
            if title_found:
                text = block.text.strip()
                if 5 <= len(text) <= 220 and not text.lower().startswith(("abstract", "keywords")):
                    return text
        for block in blocks[:5]:
            text = block.text.strip()
            if "," in text and len(text) < 180:
                return text
        return ""

    def _extract_doi(self, text: str) -> str:
        match = self.DOI_PATTERN.search(text or "")
        return match.group(0).strip() if match else ""

    def _extract_section(self, text: str, head: str, tail_candidates: tuple[str, ...]) -> str:
        if not text:
            return ""
        low = text.lower()
        start = low.find(head.lower())
        if start < 0:
            return ""
        start += len(head)
        end = len(text)
        for tail in tail_candidates:
            idx = low.find(tail.lower(), start)
            if idx > start:
                end = min(end, idx)
        section = text[start:end]
        section = normalize_whitespace(section)
        return section[:2500]
