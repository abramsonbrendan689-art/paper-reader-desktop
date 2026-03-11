from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class PaperORM(Base):
    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    display_name_cn: Mapped[str] = mapped_column(String(512), default="")
    title: Mapped[str] = mapped_column(String(1024), default="")
    title_cn: Mapped[str] = mapped_column(String(1024), default="")
    authors: Mapped[str] = mapped_column(Text, default="")
    year: Mapped[str] = mapped_column(String(16), default="")
    journal: Mapped[str] = mapped_column(String(512), default="")
    conference: Mapped[str] = mapped_column(String(512), default="")
    doi: Mapped[str] = mapped_column(String(128), default="")
    abstract: Mapped[str] = mapped_column("abstract", Text, default="")
    abstract_cn: Mapped[str] = mapped_column(Text, default="")
    keywords: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(256), default="")
    tags: Mapped[str] = mapped_column(Text, default="")
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    translation_blocks: Mapped[list["TranslationBlockORM"]] = relationship(
        back_populates="paper", cascade="all, delete-orphan"
    )
    notes: Mapped[list["NoteORM"]] = relationship(back_populates="paper", cascade="all, delete-orphan")
    citations: Mapped[list["CitationORM"]] = relationship(
        back_populates="paper", cascade="all, delete-orphan"
    )
    chat_messages: Mapped[list["ChatMessageORM"]] = relationship(
        back_populates="paper", cascade="all, delete-orphan"
    )
    reading_state: Mapped["ReadingStateORM | None"] = relationship(
        back_populates="paper", cascade="all, delete-orphan", uselist=False
    )


class TranslationBlockORM(Base):
    __tablename__ = "translation_blocks"
    __table_args__ = (
        UniqueConstraint(
            "paper_id",
            "page_number",
            "block_index",
            "provider_name",
            "source_lang",
            "target_lang",
            "checksum",
            name="uq_translation_block_cache",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), nullable=False, index=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    block_index: Mapped[int] = mapped_column(Integer, nullable=False)
    source_text: Mapped[str] = mapped_column(Text, default="")
    translated_text: Mapped[str] = mapped_column(Text, default="")
    provider_name: Mapped[str] = mapped_column(String(64), default="deepseek")
    source_lang: Mapped[str] = mapped_column(String(16), default="en")
    target_lang: Mapped[str] = mapped_column(String(16), default="zh")
    checksum: Mapped[str] = mapped_column(String(64), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    paper: Mapped[PaperORM] = relationship(back_populates="translation_blocks")


class NoteORM(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), nullable=False, index=True)
    page_number: Mapped[int] = mapped_column(Integer, default=0)
    selected_text: Mapped[str] = mapped_column(Text, default="")
    note_content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    paper: Mapped[PaperORM] = relationship(back_populates="notes")


class CitationORM(Base):
    __tablename__ = "citations"
    __table_args__ = (UniqueConstraint("paper_id", "style_name", name="uq_citation_style"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), nullable=False, index=True)
    style_name: Mapped[str] = mapped_column(String(64), nullable=False)
    citation_text: Mapped[str] = mapped_column(Text, default="")
    bibtex_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    paper: Mapped[PaperORM] = relationship(back_populates="citations")


class ChatMessageORM(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), default="user")
    content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    paper: Mapped[PaperORM] = relationship(back_populates="chat_messages")


class ReadingStateORM(Base):
    __tablename__ = "reading_states"
    __table_args__ = (UniqueConstraint("paper_id", name="uq_reading_state_paper"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), nullable=False, index=True)
    last_page: Mapped[int] = mapped_column(Integer, default=0)
    scroll_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    paper: Mapped[PaperORM] = relationship(back_populates="reading_state")


class AppSettingsORM(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    default_provider: Mapped[str] = mapped_column(String(64), default="deepseek")

    # 历史字段保留，避免旧数据库升级时报错。
    openai_api_key: Mapped[str] = mapped_column(String(512), default="")
    gemini_api_key: Mapped[str] = mapped_column(String(512), default="")
    google_translate_api_key: Mapped[str] = mapped_column(String(512), default="")

    model_name: Mapped[str] = mapped_column(String(128), default="deepseek-chat")
    use_reasoning_for_analysis: Mapped[bool] = mapped_column(Boolean, default=False)
    storage_dir: Mapped[str] = mapped_column(String(1024), default="./storage")
    cache_dir: Mapped[str] = mapped_column(String(1024), default="./cache")
    db_path: Mapped[str] = mapped_column(String(1024), default="./data/literature_reader.db")
    ui_theme: Mapped[str] = mapped_column(String(32), default="light")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
