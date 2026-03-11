from __future__ import annotations

from app.db.database import Database
from app.db.schema import AppSettingsORM
from app.models.settings import AppSettings


class SettingsRepository:
    def __init__(self, db: Database):
        self.db = db

    def get(self) -> AppSettings:
        with self.db.session_scope() as session:
            orm = session.get(AppSettingsORM, 1)
            if not orm:
                orm = AppSettingsORM(id=1)
                session.add(orm)
                session.flush()
                session.refresh(orm)

            provider_name = (orm.default_provider or "deepseek").strip().lower()
            if provider_name != "deepseek":
                provider_name = "deepseek"

            model_name = (orm.model_name or "deepseek-chat").strip() or "deepseek-chat"
            use_reasoning = bool(getattr(orm, "use_reasoning_for_analysis", False))

            return AppSettings(
                id=orm.id,
                default_provider=provider_name,
                model_name=model_name,
                use_reasoning_for_analysis=use_reasoning,
                storage_dir=orm.storage_dir,
                cache_dir=orm.cache_dir,
                db_path=orm.db_path,
                ui_theme=orm.ui_theme,
            )

    def update(self, settings: AppSettings) -> None:
        with self.db.session_scope() as session:
            orm = session.get(AppSettingsORM, 1)
            if not orm:
                orm = AppSettingsORM(id=1)
                session.add(orm)

            orm.default_provider = "deepseek"
            orm.model_name = (settings.model_name or "deepseek-chat").strip() or "deepseek-chat"
            orm.use_reasoning_for_analysis = bool(settings.use_reasoning_for_analysis)
            orm.storage_dir = settings.storage_dir
            orm.cache_dir = settings.cache_dir
            orm.db_path = settings.db_path
            orm.ui_theme = settings.ui_theme
