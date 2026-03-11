from __future__ import annotations

import re
from typing import Iterable


def normalize_whitespace(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_text_for_translation(text: str, max_chars: int = 1800) -> list[str]:
    text = normalize_whitespace(text)
    if len(text) <= max_chars:
        return [text] if text else []

    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    if not paragraphs:
        return _hard_split(text, max_chars)

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for para in paragraphs:
        if len(para) > max_chars:
            if current:
                chunks.append("\n\n".join(current))
                current = []
                current_len = 0
            chunks.extend(_hard_split(para, max_chars))
            continue
        projected = current_len + len(para) + (2 if current else 0)
        if projected > max_chars and current:
            chunks.append("\n\n".join(current))
            current = [para]
            current_len = len(para)
        else:
            current.append(para)
            current_len = projected
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def join_chunks(chunks: Iterable[str]) -> str:
    return "\n\n".join(c.strip() for c in chunks if c.strip()).strip()


def _hard_split(text: str, max_chars: int) -> list[str]:
    sentences = re.split(r"(?<=[。！？.!?])\s+", text)
    chunks: list[str] = []
    buf = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        projected = f"{buf} {sentence}".strip()
        if len(projected) <= max_chars:
            buf = projected
            continue
        if buf:
            chunks.append(buf)
        if len(sentence) <= max_chars:
            buf = sentence
        else:
            for idx in range(0, len(sentence), max_chars):
                chunks.append(sentence[idx : idx + max_chars])
            buf = ""
    if buf:
        chunks.append(buf)
    return chunks


def looks_like_reference(text: str) -> bool:
    text_lower = text.lower().strip()
    if text_lower.startswith("references"):
        return True
    return bool(re.match(r"^\[\d+\]", text_lower)) or bool(re.match(r"^\d+\.\s", text_lower))


def extract_year(text: str) -> str:
    match = re.search(r"(19|20)\d{2}", text)
    return match.group(0) if match else ""

