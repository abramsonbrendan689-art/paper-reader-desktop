from __future__ import annotations

from dataclasses import dataclass

from app.core.config import AppConfig, get_config, reload_config
from app.core.logging import logger, setup_logging
from app.db.database import Database
from app.models.settings import AppSettings
from app.providers.provider_factory import ProviderFactory
from app.repositories.chat_repository import ChatRepository
from app.repositories.citation_repository import CitationRepository
from app.repositories.note_repository import NoteRepository
from app.repositories.paper_repository import PaperRepository
from app.repositories.reading_state_repository import ReadingStateRepository
from app.repositories.settings_repository import SettingsRepository
from app.repositories.translation_repository import TranslationRepository
from app.services.ai_reading_service import AIReadingService
from app.services.chat_service import ChatService
from app.services.citation_service import CitationService
from app.services.classification_service import ClassificationService
from app.services.library_service import LibraryService
from app.services.metadata_service import MetadataService
from app.services.pdf_service import PDFService
from app.services.translation_service import TranslationService


@dataclass(slots=True)
class AppContainer:
    config: AppConfig
    db: Database

    paper_repo: PaperRepository
    translation_repo: TranslationRepository
    note_repo: NoteRepository
    citation_repo: CitationRepository
    settings_repo: SettingsRepository
    chat_repo: ChatRepository
    reading_state_repo: ReadingStateRepository

    pdf_service: PDFService
    metadata_service: MetadataService
    classification_service: ClassificationService
    translation_service: TranslationService
    ai_reading_service: AIReadingService
    chat_service: ChatService
    citation_service: CitationService
    library_service: LibraryService

    @classmethod
    def build(cls) -> "AppContainer":
        config = get_config()
        setup_logging(config.logs_dir_path, config.log_level)

        db = Database(config.db_path_path)
        db.initialize()

        paper_repo = PaperRepository(db)
        translation_repo = TranslationRepository(db)
        note_repo = NoteRepository(db)
        citation_repo = CitationRepository(db)
        settings_repo = SettingsRepository(db)
        chat_repo = ChatRepository(db)
        reading_state_repo = ReadingStateRepository(db)

        pdf_service = PDFService()
        metadata_service = MetadataService(pdf_service)
        classification_service = ClassificationService()

        effective_settings = cls._merge_settings(settings_repo.get(), config)
        providers = ProviderFactory(config).create_all(effective_settings)

        translation_service = TranslationService(
            providers=providers,
            settings_repo=settings_repo,
            translation_repo=translation_repo,
            pdf_service=pdf_service,
            max_chunk_size=config.max_text_chunk,
        )
        translation_service.use_reasoning_for_analysis = bool(
            effective_settings.use_reasoning_for_analysis
        )

        ai_reading_service = AIReadingService(translation_service, pdf_service)
        chat_service = ChatService(
            chat_repo=chat_repo,
            translation_repo=translation_repo,
            translation_service=translation_service,
            ai_reading_service=ai_reading_service,
            pdf_service=pdf_service,
        )
        citation_service = CitationService(citation_repo)
        library_service = LibraryService(
            config=config,
            paper_repo=paper_repo,
            metadata_service=metadata_service,
            classification_service=classification_service,
            translation_service=translation_service,
        )

        logger.info("App container initialized")
        translation_service.log_provider_statuses()

        return cls(
            config=config,
            db=db,
            paper_repo=paper_repo,
            translation_repo=translation_repo,
            note_repo=note_repo,
            citation_repo=citation_repo,
            settings_repo=settings_repo,
            chat_repo=chat_repo,
            reading_state_repo=reading_state_repo,
            pdf_service=pdf_service,
            metadata_service=metadata_service,
            classification_service=classification_service,
            translation_service=translation_service,
            ai_reading_service=ai_reading_service,
            chat_service=chat_service,
            citation_service=citation_service,
            library_service=library_service,
        )

    def reload_providers(self) -> None:
        self.config = reload_config()
        effective_settings = self._merge_settings(self.settings_repo.get(), self.config)
        providers = ProviderFactory(self.config).create_all(effective_settings)
        self.translation_service.providers = providers
        self.translation_service.use_reasoning_for_analysis = bool(
            effective_settings.use_reasoning_for_analysis
        )
        logger.info("Providers reloaded")
        self.translation_service.log_provider_statuses()

    @staticmethod
    def _merge_settings(db_settings: AppSettings, config: AppConfig) -> AppSettings:
        return AppSettings(
            id=1,
            default_provider="deepseek",
            model_name=(db_settings.model_name or config.deepseek_model or "deepseek-chat").strip()
            or "deepseek-chat",
            use_reasoning_for_analysis=bool(db_settings.use_reasoning_for_analysis),
            storage_dir=db_settings.storage_dir or config.storage_dir,
            cache_dir=db_settings.cache_dir or config.cache_dir,
            db_path=db_settings.db_path or config.db_path,
            ui_theme=db_settings.ui_theme or config.ui_theme,
        )
