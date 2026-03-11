from __future__ import annotations

from pathlib import Path

from app.core.config import AppConfig
from app.core.exceptions import ImportErrorDuplicate
from app.models.paper import Paper
from app.repositories.paper_repository import PaperRepository
from app.services.classification_service import ClassificationService
from app.services.metadata_service import MetadataService
from app.services.translation_service import TranslationService
from app.utils.file_utils import safe_copy, sanitize_filename


class LibraryService:
    def __init__(
        self,
        config: AppConfig,
        paper_repo: PaperRepository,
        metadata_service: MetadataService,
        classification_service: ClassificationService,
        translation_service: TranslationService,
    ):
        self.config = config
        self.paper_repo = paper_repo
        self.metadata_service = metadata_service
        self.classification_service = classification_service
        self.translation_service = translation_service

    def list_papers(self):
        return self.paper_repo.list_all()

    def search_papers(self, keyword: str):
        if not keyword.strip():
            return self.list_papers()
        return self.paper_repo.search(keyword.strip())

    def import_pdf(self, source_path: str | Path):
        src = Path(source_path)
        if not src.exists():
            raise FileNotFoundError(f"文件不存在: {src}")
        if src.suffix.lower() != ".pdf":
            raise ValueError("当前仅支持导入 PDF 文件")

        metadata = self.metadata_service.extract_metadata(src)
        duplicate = self.paper_repo.find_possible_duplicate(
            title=metadata.get("title", ""),
            year=metadata.get("year", ""),
            doi=metadata.get("doi", ""),
        )
        if duplicate:
            raise ImportErrorDuplicate(f"疑似重复文献: {duplicate.title or duplicate.original_filename}")

        preferred_name = metadata.get("title") or src.stem
        copied_path = safe_copy(src, self.config.storage_dir_path, preferred_name)

        title_cn = self._translate_title(metadata.get("title", ""))
        display_name_cn = self._build_display_name_cn(
            year=metadata.get("year", ""),
            authors=metadata.get("authors", ""),
            title_cn=title_cn or metadata.get("title", ""),
            fallback=src.stem,
        )

        paper = Paper(
            original_filename=src.name,
            display_name_cn=display_name_cn,
            title=metadata.get("title", src.stem),
            title_cn=title_cn,
            authors=metadata.get("authors", ""),
            year=metadata.get("year", ""),
            journal=metadata.get("journal", ""),
            conference=metadata.get("conference", ""),
            doi=metadata.get("doi", ""),
            abstract=metadata.get("abstract", ""),
            abstract_cn="",
            keywords=metadata.get("keywords", ""),
            category=self.classification_service.classify(metadata),
            tags="",
            file_path=str(copied_path),
        )
        return self.paper_repo.create(paper)

    def import_folder(self, folder_path: str | Path) -> tuple[list, list[str]]:
        folder = Path(folder_path)
        if not folder.exists():
            raise FileNotFoundError(f"文件夹不存在: {folder}")

        created = []
        errors: list[str] = []
        for pdf in folder.rglob("*.pdf"):
            try:
                created.append(self.import_pdf(pdf))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{pdf.name}: {exc}")
        return created, errors

    def _translate_title(self, title: str) -> str:
        if not title.strip():
            return ""
        try:
            translated = self.translation_service.translate_text(
                title,
                source_lang="en",
                target_lang="zh",
                options={"glossary": "标题翻译保持简洁准确"},
            )
            return translated.strip()
        except Exception:  # noqa: BLE001
            return ""

    def _build_display_name_cn(self, year: str, authors: str, title_cn: str, fallback: str) -> str:
        first_author = authors.split(",")[0].split(";")[0].strip() if authors else "未知作者"
        short_title = sanitize_filename((title_cn or fallback)[:30])
        if year:
            return f"{year}_{first_author}_{short_title}"
        return f"{first_author}_{short_title}"
