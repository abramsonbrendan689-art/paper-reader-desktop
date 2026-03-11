from __future__ import annotations

from sqlalchemy import or_, select

from app.db.database import Database
from app.db.schema import PaperORM
from app.models.paper import Paper


class PaperRepository:
    def __init__(self, db: Database):
        self.db = db

    def list_all(self) -> list[PaperORM]:
        with self.db.session_scope() as session:
            stmt = select(PaperORM).order_by(PaperORM.updated_at.desc())
            return list(session.scalars(stmt))

    def search(self, keyword: str) -> list[PaperORM]:
        with self.db.session_scope() as session:
            key = f"%{keyword}%"
            stmt = (
                select(PaperORM)
                .where(
                    or_(
                        PaperORM.title.ilike(key),
                        PaperORM.title_cn.ilike(key),
                        PaperORM.authors.ilike(key),
                        PaperORM.keywords.ilike(key),
                        PaperORM.display_name_cn.ilike(key),
                    )
                )
                .order_by(PaperORM.updated_at.desc())
            )
            return list(session.scalars(stmt))

    def get_by_id(self, paper_id: int) -> PaperORM | None:
        with self.db.session_scope() as session:
            return session.get(PaperORM, paper_id)

    def get_by_file_path(self, file_path: str) -> PaperORM | None:
        with self.db.session_scope() as session:
            stmt = select(PaperORM).where(PaperORM.file_path == file_path)
            return session.scalars(stmt).first()

    def find_possible_duplicate(self, title: str, year: str, doi: str) -> PaperORM | None:
        with self.db.session_scope() as session:
            if doi:
                by_doi = session.scalars(select(PaperORM).where(PaperORM.doi == doi)).first()
                if by_doi:
                    return by_doi
            if title:
                stmt = select(PaperORM).where(PaperORM.title == title, PaperORM.year == year)
                return session.scalars(stmt).first()
            return None

    def create(self, paper: Paper) -> PaperORM:
        with self.db.session_scope() as session:
            orm = PaperORM(
                original_filename=paper.original_filename,
                display_name_cn=paper.display_name_cn,
                title=paper.title,
                title_cn=paper.title_cn,
                authors=paper.authors,
                year=paper.year,
                journal=paper.journal,
                conference=paper.conference,
                doi=paper.doi,
                abstract=paper.abstract,
                abstract_cn=paper.abstract_cn,
                keywords=paper.keywords,
                category=paper.category,
                tags=paper.tags,
                file_path=paper.file_path,
            )
            session.add(orm)
            session.flush()
            session.refresh(orm)
            return orm

    def update_names(self, paper_id: int, title_cn: str, display_name_cn: str) -> None:
        with self.db.session_scope() as session:
            orm = session.get(PaperORM, paper_id)
            if not orm:
                return
            orm.title_cn = title_cn
            orm.display_name_cn = display_name_cn

