from __future__ import annotations

from sqlalchemy import select

from app.db.database import Database
from app.db.schema import NoteORM
from app.models.note import Note


class NoteRepository:
    def __init__(self, db: Database):
        self.db = db

    def list_by_paper(self, paper_id: int) -> list[NoteORM]:
        with self.db.session_scope() as session:
            stmt = (
                select(NoteORM)
                .where(NoteORM.paper_id == paper_id)
                .order_by(NoteORM.updated_at.desc())
            )
            return list(session.scalars(stmt))

    def create(self, note: Note) -> NoteORM:
        with self.db.session_scope() as session:
            orm = NoteORM(
                paper_id=note.paper_id,
                page_number=note.page_number,
                selected_text=note.selected_text,
                note_content=note.note_content,
            )
            session.add(orm)
            session.flush()
            session.refresh(orm)
            return orm

