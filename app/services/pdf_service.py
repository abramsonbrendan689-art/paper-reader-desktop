from __future__ import annotations

import html
import re
from collections import OrderedDict
from pathlib import Path

import fitz

from app.models.paper import PaperBlock
from app.utils.text_utils import looks_like_reference, normalize_whitespace


class PDFService:
    def __init__(self, max_render_cache: int = 120):
        self.max_render_cache = max_render_cache
        self._pixmap_cache: OrderedDict[tuple[str, int, int], fitz.Pixmap] = OrderedDict()

    def page_count(self, pdf_path: str | Path) -> int:
        with fitz.open(pdf_path) as doc:
            return len(doc)

    def get_page_size(self, pdf_path: str | Path, page_number: int) -> tuple[float, float]:
        with fitz.open(pdf_path) as doc:
            rect = doc[page_number].rect
            return float(rect.width), float(rect.height)

    def get_page_sizes(self, pdf_path: str | Path) -> list[tuple[float, float]]:
        with fitz.open(pdf_path) as doc:
            sizes: list[tuple[float, float]] = []
            for page in doc:
                rect = page.rect
                sizes.append((float(rect.width), float(rect.height)))
            return sizes

    def render_page(self, pdf_path: str | Path, page_number: int, zoom: float = 1.4) -> fitz.Pixmap:
        zoom_key = max(10, int(round(zoom * 100)))
        key = (str(Path(pdf_path).resolve()), int(page_number), zoom_key)
        cached = self._pixmap_cache.get(key)
        if cached is not None:
            self._pixmap_cache.move_to_end(key)
            return cached

        with fitz.open(pdf_path) as doc:
            page = doc[page_number]
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)

        self._pixmap_cache[key] = pix
        self._pixmap_cache.move_to_end(key)
        while len(self._pixmap_cache) > self.max_render_cache:
            self._pixmap_cache.popitem(last=False)
        return pix

    def clear_render_cache(self, pdf_path: str | Path | None = None) -> None:
        if pdf_path is None:
            self._pixmap_cache.clear()
            return
        target = str(Path(pdf_path).resolve())
        keys = [k for k in self._pixmap_cache.keys() if k[0] == target]
        for key in keys:
            self._pixmap_cache.pop(key, None)

    def extract_page_blocks(self, pdf_path: str | Path, page_number: int) -> list[PaperBlock]:
        with fitz.open(pdf_path) as doc:
            page = doc[page_number]
            page_height = page.rect.height
            payload = page.get_text("dict")

        blocks: list[PaperBlock] = []
        for block_idx, block in enumerate(payload.get("blocks", [])):
            if block.get("type") != 0:
                continue

            lines = block.get("lines", [])
            span_texts: list[str] = []
            font_sizes: list[float] = []
            span_count = 0
            for line in lines:
                spans = line.get("spans", [])
                for span in spans:
                    text = (span.get("text") or "").strip()
                    if not text:
                        continue
                    span_texts.append(text)
                    size = float(span.get("size") or 0.0)
                    if size > 0:
                        font_sizes.append(size)
                    span_count += 1

            full_text = normalize_whitespace(" ".join(span_texts))
            if not full_text:
                continue

            x0, y0, x1, y1 = block.get("bbox", (0, 0, 0, 0))
            avg_size = sum(font_sizes) / len(font_sizes) if font_sizes else 10.0
            block_type = "body"
            lowered = full_text.lower()

            if y1 < page_height * 0.08 and avg_size <= 9:
                block_type = "header"
            elif y0 > page_height * 0.9 and avg_size <= 9:
                block_type = "footer"
            elif looks_like_reference(full_text):
                block_type = "reference"
            elif "=" in full_text and len(full_text.split()) < 12:
                block_type = "formula"
            elif avg_size >= 12.5 and len(full_text) < 180:
                block_type = "heading"
            elif lowered.startswith("fig.") or lowered.startswith("figure") or lowered.startswith("table"):
                block_type = "figure_caption"

            blocks.append(
                PaperBlock(
                    page_number=page_number,
                    block_index=block_idx,
                    text=full_text,
                    bbox=(x0, y0, x1, y1),
                    avg_font_size=avg_size,
                    span_count=span_count,
                    block_type=block_type,
                    extra={"raw_block_type": block.get("type")},
                )
            )
        return blocks

    def extract_document_text(self, pdf_path: str | Path, max_pages: int | None = None) -> str:
        with fitz.open(pdf_path) as doc:
            page_total = len(doc)
            limit = min(max_pages or page_total, page_total)
            chunks: list[str] = []
            for page_idx in range(limit):
                text = doc[page_idx].get_text("text")
                if text.strip():
                    chunks.append(text.strip())
        return "\n\n".join(chunks)

    def is_scanned_pdf(self, pdf_path: str | Path, sample_pages: int = 3) -> bool:
        with fitz.open(pdf_path) as doc:
            limit = min(sample_pages, len(doc))
            text_count = 0
            for idx in range(limit):
                if doc[idx].get_text("text").strip():
                    text_count += 1
            return text_count == 0

    def should_skip_translation(self, block: PaperBlock) -> bool:
        return block.block_type in {"header", "footer", "reference", "formula"}

    def block_to_minimal_html(self, block: PaperBlock) -> str:
        """
        Minimal HTML wrapper to preserve lightweight structure while translating.
        Allowed tags: <p>, <br>, <b>, <i>, <sup>, <sub>, <span>
        """
        safe_text = html.escape(block.text)
        safe_text = safe_text.replace("\n", "<br>")
        return f"<p><span>{safe_text}</span></p>"

    def html_to_display_text(self, translated_html: str) -> str:
        if not translated_html:
            return ""
        text = translated_html
        text = re.sub(r"<\s*br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        text = html.unescape(text)
        return normalize_whitespace(text)
