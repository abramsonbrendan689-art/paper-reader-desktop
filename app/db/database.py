from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.db.schema import AppSettingsORM, Base


class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{db_path.as_posix()}", echo=False, future=True)
        self.session_factory = sessionmaker(
            bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False
        )

    def initialize(self) -> None:
        Base.metadata.create_all(self.engine)
        self._ensure_compat_columns()

        with self.session_scope() as session:
            if not session.get(AppSettingsORM, 1):
                session.add(AppSettingsORM(id=1))

    def _ensure_compat_columns(self) -> None:
        # 兼容已有数据库：新增配置列时自动补齐，避免首次启动报错。
        with self.engine.begin() as conn:
            columns = {
                row[1] for row in conn.execute(text("PRAGMA table_info(app_settings)"))
            }
            if "use_reasoning_for_analysis" not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE app_settings "
                        "ADD COLUMN use_reasoning_for_analysis INTEGER DEFAULT 0"
                    )
                )

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
