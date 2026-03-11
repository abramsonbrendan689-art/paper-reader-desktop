from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from app.models.paper import PaperBlock
from app.services.translation_service import TranslationResult, TranslationService


class TranslateWorker(QThread):
    block_ready = Signal(object)
    page_done = Signal(int)
    status = Signal(str)
    result_ready = Signal(list)
    error = Signal(str)

    def __init__(
        self,
        translation_service: TranslationService,
        paper_id: int,
        page_blocks_map: dict[int, list[PaperBlock]],
        provider_name: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.translation_service = translation_service
        self.paper_id = paper_id
        self.page_blocks_map = page_blocks_map
        self.provider_name = provider_name

    def run(self) -> None:
        try:
            provider = self.translation_service.resolve_provider(self.provider_name)
            all_results: list[TranslationResult] = []

            for page_number in sorted(self.page_blocks_map.keys()):
                if self.isInterruptionRequested():
                    self.status.emit("翻译任务已取消")
                    break
                blocks = self.page_blocks_map.get(page_number) or []
                self.status.emit(f"正在翻译第 {page_number + 1} 页（共 {len(blocks)} 个块）...")

                for result in self.translation_service.translate_page_blocks_stream(
                    paper_id=self.paper_id,
                    page_number=page_number,
                    blocks=blocks,
                    provider_name=provider.name,
                ):
                    if self.isInterruptionRequested():
                        self.status.emit("翻译任务已取消")
                        break
                    all_results.append(result)
                    self.block_ready.emit(result)

                if self.isInterruptionRequested():
                    break
                self.page_done.emit(page_number)

            self.result_ready.emit(all_results)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(f"翻译任务失败: {exc}")
