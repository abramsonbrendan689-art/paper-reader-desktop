from __future__ import annotations

from sqlalchemy import select

from app.db.database import Database
from app.db.schema import ReadingStateORM
from app.models.reading_state import ReadingState


class ReadingStateRepository:
    def __init__(self, db: Database):
        self.db = db

    def get_by_paper(self, paper_id: int) -> ReadingStateORM | None:
        with self.db.session_scope() as session:
            stmt = select(ReadingStateORM).where(ReadingStateORM.paper_id == paper_id)
            return session.scalars(stmt).first()

    def upsert(self, state: ReadingState) -> ReadingStateORM:
        with self.db.session_scope() as session:
            stmt = select(ReadingStateORM).where(ReadingStateORM.paper_id == state.paper_id)
            orm = session.scalars(stmt).first()
            if orm:
                orm.last_page = max(0, state.last_page)
                orm.scroll_ratio = max(0.0, min(1.0, float(state.scroll_ratio)))
                session.flush()
                session.refresh(orm)
                return orm

            orm = ReadingStateORM(
                paper_id=state.paper_id,
                last_page=max(0, state.last_page),
                scroll_ratio=max(0.0, min(1.0, float(state.scroll_ratio))),
            )
            session.add(orm)
            session.flush()
            session.refresh(orm)
            return orm
