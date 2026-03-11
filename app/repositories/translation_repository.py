from __future__ import annotations

from sqlalchemy import select

from app.db.database import Database
from app.db.schema import TranslationBlockORM
from app.models.translation_block import TranslationBlock


class TranslationRepository:
    def __init__(self, db: Database):
        self.db = db

    def get_page_blocks(self, paper_id: int, page_number: int, provider_name: str) -> list[TranslationBlockORM]:
        with self.db.session_scope() as session:
            stmt = (
                select(TranslationBlockORM)
                .where(
                    TranslationBlockORM.paper_id == paper_id,
                    TranslationBlockORM.page_number == page_number,
                    TranslationBlockORM.provider_name == provider_name,
                )
                .order_by(TranslationBlockORM.block_index.asc())
            )
            return list(session.scalars(stmt))

    def get_cached(
        self,
        paper_id: int,
        page_number: int,
        block_index: int,
        provider_name: str,
        source_lang: str,
        target_lang: str,
        checksum: str,
    ) -> TranslationBlockORM | None:
        with self.db.session_scope() as session:
            stmt = select(TranslationBlockORM).where(
                TranslationBlockORM.paper_id == paper_id,
                TranslationBlockORM.page_number == page_number,
                TranslationBlockORM.block_index == block_index,
                TranslationBlockORM.provider_name == provider_name,
                TranslationBlockORM.source_lang == source_lang,
                TranslationBlockORM.target_lang == target_lang,
                TranslationBlockORM.checksum == checksum,
            )
            return session.scalars(stmt).first()

    def save_block(self, block: TranslationBlock) -> TranslationBlockORM:
        with self.db.session_scope() as session:
            existing = session.scalars(
                select(TranslationBlockORM).where(
                    TranslationBlockORM.paper_id == block.paper_id,
                    TranslationBlockORM.page_number == block.page_number,
                    TranslationBlockORM.block_index == block.block_index,
                    TranslationBlockORM.provider_name == block.provider_name,
                    TranslationBlockORM.source_lang == block.source_lang,
                    TranslationBlockORM.target_lang == block.target_lang,
                    TranslationBlockORM.checksum == block.checksum,
                )
            ).first()

            if existing:
                existing.translated_text = block.translated_text
                session.flush()
                session.refresh(existing)
                return existing

            orm = TranslationBlockORM(
                paper_id=block.paper_id,
                page_number=block.page_number,
                block_index=block.block_index,
                source_text=block.source_text,
                translated_text=block.translated_text,
                provider_name=block.provider_name,
                source_lang=block.source_lang,
                target_lang=block.target_lang,
                checksum=block.checksum,
            )
            session.add(orm)
            session.flush()
            session.refresh(orm)
            return orm

