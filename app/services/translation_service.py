from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from typing import Any

from app.core.exceptions import ProviderUnavailableError
from app.core.logging import logger
from app.models.paper import PaperBlock
from app.models.translation_block import TranslationBlock
from app.providers.base_provider import BaseProvider
from app.repositories.settings_repository import SettingsRepository
from app.repositories.translation_repository import TranslationRepository
from app.services.pdf_service import PDFService
from app.utils.checksum import md5_text
from app.utils.text_utils import join_chunks, split_text_for_translation


@dataclass(slots=True)
class TranslationResult:
    page_number: int
    block_index: int
    source_text: str
    translated_text: str
    block_type: str
    from_cache: bool


class TranslationService:
    def __init__(
        self,
        providers: dict[str, BaseProvider],
        settings_repo: SettingsRepository,
        translation_repo: TranslationRepository,
        pdf_service: PDFService,
        max_chunk_size: int = 1800,
        page_batch_size: int = 12,
    ):
        self.providers = providers
        self.settings_repo = settings_repo
        self.translation_repo = translation_repo
        self.pdf_service = pdf_service
        self.max_chunk_size = max_chunk_size
        self.page_batch_size = page_batch_size
        self.use_reasoning_for_analysis = False

    def get_default_provider_name(self) -> str:
        return "deepseek"

    def get_default_model_name(self, reasoning: bool = False) -> str:
        provider = self.providers.get("deepseek")
        if not provider:
            return "deepseek-chat"
        return provider.get_model_name(reasoning=reasoning)

    def get_provider_statuses(self) -> dict[str, tuple[bool, str]]:
        status: dict[str, tuple[bool, str]] = {}
        for name, provider in self.providers.items():
            ok, message = provider.test_connection()
            status[name] = (ok, message)
        return status

    def log_provider_statuses(self) -> None:
        for name, (ok, message) in self.get_provider_statuses().items():
            if ok:
                logger.info("Provider [{}] available: {}", name, message)
            else:
                logger.warning("Provider [{}] unavailable: {}", name, message)

    def resolve_provider(self, provider_name: str | None = None) -> BaseProvider:
        target = (provider_name or "deepseek").strip().lower()
        provider = self.providers.get(target)
        if not provider:
            raise ProviderUnavailableError("DeepSeek Provider 未初始化")
        if not provider.is_available():
            raise ProviderUnavailableError(provider.availability_reason() or "DeepSeek 未配置")
        return provider

    def set_analysis_reasoning(self, enabled: bool) -> None:
        self.use_reasoning_for_analysis = bool(enabled)

    def translate_text(
        self,
        text: str,
        provider_name: str | None = None,
        source_lang: str = "en",
        target_lang: str = "zh",
        options: dict[str, Any] | None = None,
    ) -> str:
        if not text.strip():
            return ""

        provider = self.resolve_provider(provider_name)
        chunks = split_text_for_translation(text, self.max_chunk_size)
        translated: list[str] = []
        for chunk in chunks:
            translated.append(
                provider.translate(
                    chunk,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    options=options,
                )
            )
        return join_chunks(translated)

    def translate_page_blocks(
        self,
        paper_id: int,
        page_number: int,
        blocks: list[PaperBlock],
        provider_name: str | None = None,
        source_lang: str = "en",
        target_lang: str = "zh",
    ) -> list[TranslationResult]:
        return list(
            self.translate_page_blocks_stream(
                paper_id=paper_id,
                page_number=page_number,
                blocks=blocks,
                provider_name=provider_name,
                source_lang=source_lang,
                target_lang=target_lang,
            )
        )

    def translate_page_blocks_stream(
        self,
        paper_id: int,
        page_number: int,
        blocks: list[PaperBlock],
        provider_name: str | None = None,
        source_lang: str = "en",
        target_lang: str = "zh",
    ) -> Generator[TranslationResult, None, None]:
        provider = self.resolve_provider(provider_name)
        active_provider_name = provider.name
        model_name = provider.get_model_name(reasoning=False)

        to_translate: list[dict[str, Any]] = []

        for block in blocks:
            checksum = md5_text(f"{model_name}|{target_lang}|{block.text}")

            cached = self.translation_repo.get_cached(
                paper_id=paper_id,
                page_number=page_number,
                block_index=block.block_index,
                provider_name=active_provider_name,
                source_lang=source_lang,
                target_lang=target_lang,
                checksum=checksum,
            )
            if cached:
                yield TranslationResult(
                    page_number=page_number,
                    block_index=block.block_index,
                    source_text=block.text,
                    translated_text=cached.translated_text,
                    block_type=block.block_type,
                    from_cache=True,
                )
                continue

            if self.pdf_service.should_skip_translation(block):
                translated_text = self._special_block_text(block)
                self._save_translation(
                    paper_id=paper_id,
                    page_number=page_number,
                    block=block,
                    translated_text=translated_text,
                    provider_name=active_provider_name,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    checksum=checksum,
                )
                yield TranslationResult(
                    page_number=page_number,
                    block_index=block.block_index,
                    source_text=block.text,
                    translated_text=translated_text,
                    block_type=block.block_type,
                    from_cache=False,
                )
                continue

            to_translate.append(
                {
                    "block": block,
                    "checksum": checksum,
                    "payload": {
                        "text": self.pdf_service.block_to_minimal_html(block),
                        "plain_text": block.text,
                        "mime_type": "text/html",
                    },
                }
            )

        for batch in self._chunk_items(to_translate, self.page_batch_size):
            payloads = [item["payload"] for item in batch]
            translated_list: list[str]
            try:
                translated_list = provider.translate_blocks(
                    blocks=payloads,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    options={"reasoning": False},
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Batch translation failed on page {}: {}", page_number, exc)
                translated_list = [f"翻译失败: {exc}" for _ in batch]

            for idx, item in enumerate(batch):
                block = item["block"]
                checksum = item["checksum"]
                translated_text = (
                    translated_list[idx]
                    if idx < len(translated_list)
                    else "翻译失败: 返回数量不匹配"
                )

                self._save_translation(
                    paper_id=paper_id,
                    page_number=page_number,
                    block=block,
                    translated_text=translated_text,
                    provider_name=active_provider_name,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    checksum=checksum,
                )

                yield TranslationResult(
                    page_number=page_number,
                    block_index=block.block_index,
                    source_text=block.text,
                    translated_text=translated_text,
                    block_type=block.block_type,
                    from_cache=False,
                )

    def _save_translation(
        self,
        paper_id: int,
        page_number: int,
        block: PaperBlock,
        translated_text: str,
        provider_name: str,
        source_lang: str,
        target_lang: str,
        checksum: str,
    ) -> None:
        record = TranslationBlock(
            paper_id=paper_id,
            page_number=page_number,
            block_index=block.block_index,
            source_text=block.text,
            translated_text=translated_text,
            provider_name=provider_name,
            source_lang=source_lang,
            target_lang=target_lang,
            checksum=checksum,
        )
        self.translation_repo.save_block(record)

    @staticmethod
    def _special_block_text(block: PaperBlock) -> str:
        if block.block_type in {"header", "footer"}:
            return "[页眉/页脚已过滤]"
        if block.block_type == "formula":
            return "[公式区域] 公式本体不翻译，仅保留上下文说明。"
        if block.block_type == "reference":
            return "[参考文献区域] 默认不按正文翻译。"
        return ""

    @staticmethod
    def _chunk_items(items: list[dict[str, Any]], chunk_size: int) -> list[list[dict[str, Any]]]:
        if chunk_size <= 0:
            chunk_size = 1
        return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]
