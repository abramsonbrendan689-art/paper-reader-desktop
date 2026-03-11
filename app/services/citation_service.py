from __future__ import annotations

import re
from dataclasses import dataclass

from app.db.schema import PaperORM
from app.models.citation import CitationResult
from app.repositories.citation_repository import CitationRepository


@dataclass(slots=True)
class AuthorName:
    raw: str
    family: str
    initials: str


class CitationService:
    STYLES = ("GB/T 7714", "APA", "MLA", "Chicago", "BibTeX")

    def __init__(self, citation_repo: CitationRepository):
        self.citation_repo = citation_repo

    def generate_all(self, paper: PaperORM) -> dict[str, CitationResult]:
        styles: dict[str, CitationResult] = {}
        for style in self.STYLES:
            citation = self._generate_by_style(paper, style)
            self.citation_repo.upsert(paper.id, citation)
            styles[style] = citation
        return styles

    def _generate_by_style(self, paper: PaperORM, style: str) -> CitationResult:
        authors = self._parse_authors(paper.authors)
        if style == "APA":
            text = self._format_apa(paper, authors)
        elif style == "MLA":
            text = self._format_mla(paper, authors)
        elif style == "Chicago":
            text = self._format_chicago(paper, authors)
        elif style == "GB/T 7714":
            text = self._format_gbt(paper, authors)
        elif style == "BibTeX":
            text = self._format_bibtex(paper, authors)
        else:
            text = paper.title

        bibtex_text = self._format_bibtex(paper, authors)
        return CitationResult(style_name=style, citation_text=text, bibtex_text=bibtex_text)

    def _parse_authors(self, raw: str) -> list[AuthorName]:
        if not raw.strip():
            return []
        chunks = re.split(r";|, and | and |\n", raw)
        out: list[AuthorName] = []
        for chunk in chunks:
            name = chunk.strip(" ,")
            if not name:
                continue
            parts = name.split()
            family = parts[-1] if parts else name
            initials = "".join(f"{p[0].upper()}." for p in parts[:-1] if p)
            out.append(AuthorName(raw=name, family=family, initials=initials))
        return out

    def _author_list(self, authors: list[AuthorName], max_count: int = 3) -> str:
        if not authors:
            return "Unknown"
        if len(authors) <= max_count:
            return ", ".join(a.raw for a in authors)
        return ", ".join(a.raw for a in authors[:max_count]) + ", et al."

    def _format_apa(self, paper: PaperORM, authors: list[AuthorName]) -> str:
        if authors:
            names = ", ".join(f"{a.family}, {a.initials}" for a in authors[:6])
        else:
            names = "Unknown"
        year = paper.year or "n.d."
        source = paper.journal or paper.conference or "Unknown Venue"
        return f"{names} ({year}). {paper.title or 'Untitled'}. {source}."

    def _format_mla(self, paper: PaperORM, authors: list[AuthorName]) -> str:
        names = self._author_list(authors)
        source = paper.journal or paper.conference or "Unknown Venue"
        year = paper.year or "n.d."
        return f'{names}. "{paper.title or "Untitled"}." {source}, {year}.'

    def _format_chicago(self, paper: PaperORM, authors: list[AuthorName]) -> str:
        names = self._author_list(authors)
        source = paper.journal or paper.conference or "Unknown Venue"
        year = paper.year or "n.d."
        return f"{names}. {year}. \"{paper.title or 'Untitled'}.\" {source}."

    def _format_gbt(self, paper: PaperORM, authors: list[AuthorName]) -> str:
        names = self._author_list(authors)
        source = paper.journal or paper.conference or "Unknown Venue"
        year = paper.year or "n.d."
        return f"{names}. {paper.title or 'Untitled'}[J]. {source}, {year}."

    def _format_bibtex(self, paper: PaperORM, authors: list[AuthorName]) -> str:
        key = f"{(authors[0].family if authors else 'unknown').lower()}{paper.year or 'nd'}"
        venue = paper.journal or paper.conference
        entry_type = "article" if paper.journal else "inproceedings" if paper.conference else "misc"
        author_text = " and ".join(a.raw for a in authors) if authors else "Unknown"
        lines = [
            f"@{entry_type}{{{key},",
            f"  title = {{{paper.title or 'Untitled'}}},",
            f"  author = {{{author_text}}},",
        ]
        if paper.year:
            lines.append(f"  year = {{{paper.year}}},")
        if paper.journal:
            lines.append(f"  journal = {{{paper.journal}}},")
        if paper.conference:
            lines.append(f"  booktitle = {{{paper.conference}}},")
        if paper.doi:
            lines.append(f"  doi = {{{paper.doi}}},")
        lines.append("}")
        return "\n".join(lines)

