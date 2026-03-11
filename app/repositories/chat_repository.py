from __future__ import annotations

from sqlalchemy import select

from app.db.database import Database
from app.db.schema import ChatMessageORM
from app.models.chat_message import ChatMessage


class ChatRepository:
    def __init__(self, db: Database):
        self.db = db

    def list_by_paper(self, paper_id: int, limit: int = 200) -> list[ChatMessageORM]:
        with self.db.session_scope() as session:
            stmt = (
                select(ChatMessageORM)
                .where(ChatMessageORM.paper_id == paper_id)
                .order_by(ChatMessageORM.created_at.asc(), ChatMessageORM.id.asc())
                .limit(limit)
            )
            return list(session.scalars(stmt))

    def create(self, message: ChatMessage) -> ChatMessageORM:
        with self.db.session_scope() as session:
            orm = ChatMessageORM(
                paper_id=message.paper_id,
                role=message.role,
                content=message.content,
            )
            session.add(orm)
            session.flush()
            session.refresh(orm)
            return orm

    def clear_by_paper(self, paper_id: int) -> None:
        with self.db.session_scope() as session:
            rows = session.scalars(select(ChatMessageORM).where(ChatMessageORM.paper_id == paper_id)).all()
            for row in rows:
                session.delete(row)
