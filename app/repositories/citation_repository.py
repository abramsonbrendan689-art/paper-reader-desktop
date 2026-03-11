from __future__ import annotations

from sqlalchemy import select

from app.db.database import Database
from app.db.schema import CitationORM
from app.models.citation import CitationResult


class CitationRepository:
    def __init__(self, db: Database):
        self.db = db

    def get_by_style(self, paper_id: int, style_name: str) -> CitationORM | None:
        with self.db.session_scope() as session:
            stmt = select(CitationORM).where(
                CitationORM.paper_id == paper_id, CitationORM.style_name == style_name
            )
            return session.scalars(stmt).first()

    def upsert(self, paper_id: int, citation: CitationResult) -> CitationORM:
        with self.db.session_scope() as session:
            existing = session.scalars(
                select(CitationORM).where(
                    CitationORM.paper_id == paper_id,
                    CitationORM.style_name == citation.style_name,
                )
            ).first()
            if existing:
                existing.citation_text = citation.citation_text
                existing.bibtex_text = citation.bibtex_text
                session.flush()
                session.refresh(existing)
                return existing

            orm = CitationORM(
                paper_id=paper_id,
                style_name=citation.style_name,
                citation_text=citation.citation_text,
                bibtex_text=citation.bibtex_text,
            )
            session.add(orm)
            session.flush()
            session.refresh(orm)
            return orm

