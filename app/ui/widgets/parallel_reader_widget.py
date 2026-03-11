from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QSplitter, QStackedWidget, QVBoxLayout, QWidget

from app.models.paper import PaperBlock
from app.services.pdf_service import PDFService
from app.services.translation_service import TranslationResult
from app.ui.theme import apply_elevation
from app.ui.widgets.source_pdf_reader import SourcePdfReader
from app.ui.widgets.translated_document_reader import TranslatedDocumentReader
from app.ui.widgets.translation_panel import TranslationPanel


class ParallelReaderWidget(QWidget):
    current_page_changed = Signal(int)
    visible_pages_changed = Signal(list)
    scroll_ratio_changed = Signal(float)
    selected_text_changed = Signal(str)
    reader_action_requested = Signal(str, str)

    MODE_PARALLEL = "parallel"
    MODE_SOURCE = "source_only"
    MODE_TRANSLATED = "translated_only"
    MODE_STRUCTURE = "structure"

    def __init__(self, pdf_service: PDFService, parent=None):
        super().__init__(parent)
        self.pdf_service = pdf_service
        self.sync_enabled = True
        self.current_mode = self.MODE_PARALLEL
        self._selected_text = ""
        self._build_ui()
        self._bind_events()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.surface = QFrame()
        self.surface.setObjectName("ReaderMainSurface")
        apply_elevation(self.surface, "card")
        surface_layout = QVBoxLayout(self.surface)
        surface_layout.setContentsMargins(8, 8, 8, 8)
        surface_layout.setSpacing(0)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(12)

        self.source_reader = SourcePdfReader(self.pdf_service)
        self.translated_stack = QStackedWidget()
        self.translated_reader = TranslatedDocumentReader()
        self.structure_panel = TranslationPanel()
        self.translated_stack.addWidget(self.translated_reader)
        self.translated_stack.addWidget(self.structure_panel)
        self.translated_stack.setCurrentIndex(0)

        self.source_shell = self._build_reader_shell(
            title="原文 PDF",
            subtitle="连续滚动阅读，默认适合宽度",
            content_widget=self.source_reader,
        )
        self.translated_shell = self._build_reader_shell(
            title="中文译文",
            subtitle="按页面组织的中文文档流",
            content_widget=self.translated_stack,
        )

        self.splitter.addWidget(self.source_shell)
        self.splitter.addWidget(self.translated_shell)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([960, 1040])

        surface_layout.addWidget(self.splitter, 1)
        root.addWidget(self.surface, 1)

    def _build_reader_shell(self, title: str, subtitle: str, content_widget: QWidget) -> QFrame:
        shell = QFrame()
        shell.setObjectName("ReaderColumnShell")
        layout = QVBoxLayout(shell)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        header = QFrame()
        header.setObjectName("ReaderColumnHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(8, 6, 8, 8)
        header_layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setObjectName("ReaderColumnTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("ReaderColumnSubtitle")

        header_layout.addWidget(title_label)
        header_layout.addWidget(subtitle_label)

        layout.addWidget(header)
        layout.addWidget(content_widget, 1)
        return shell

    def _bind_events(self) -> None:
        self.source_reader.current_page_changed.connect(self._on_source_page_changed)
        self.source_reader.visible_pages_changed.connect(self.visible_pages_changed.emit)
        self.source_reader.scroll_ratio_changed.connect(self.scroll_ratio_changed.emit)
        self.source_reader.page_anchor_changed.connect(self._on_source_page_anchor_changed)

        self.translated_reader.current_page_changed.connect(self._on_translated_page_changed)
        self.translated_reader.selected_text_changed.connect(self._on_selected_text_changed)
        self.translated_reader.action_requested.connect(self.reader_action_requested.emit)
        self.structure_panel.selected_text_changed.connect(self._on_selected_text_changed)

    def load_pdf(self, pdf_path: str, initial_page: int = 0, initial_scroll_ratio: float = 0.0) -> None:
        self.source_reader.load_pdf(
            pdf_path=pdf_path,
            initial_page=initial_page,
            initial_scroll_ratio=initial_scroll_ratio,
        )
        self.translated_reader.initialize_document(self.source_reader.get_page_count())

    def clear(self) -> None:
        self.translated_reader.clear_document()
        self.structure_panel.show_block_source_only([])
        self._selected_text = ""

    def set_page_blocks(self, page_number: int, blocks: list[PaperBlock]) -> None:
        self.translated_reader.set_page_blocks(page_number, blocks, results=None)
        if page_number == self.get_current_page():
            self.structure_panel.show_block_source_only(blocks)

    def set_page_translations(
        self,
        page_number: int,
        blocks: list[PaperBlock],
        results: list[TranslationResult],
    ) -> None:
        self.translated_reader.set_page_blocks(page_number, blocks, results=results)
        if page_number == self.get_current_page():
            self.structure_panel.show_translations(blocks, results)

    def update_translation_result(self, result: TranslationResult) -> None:
        self.translated_reader.update_block_translation(result)
        if result.page_number == self.get_current_page():
            self.structure_panel.update_translation_result(result)

    def get_current_page(self) -> int:
        return self.source_reader.get_current_page()

    def get_page_count(self) -> int:
        return self.source_reader.get_page_count()

    def get_visible_pages(self) -> list[int]:
        return self.source_reader.get_visible_page_numbers()

    def get_scroll_ratio(self) -> float:
        return self.source_reader.get_scroll_ratio()

    def get_selected_source_text(self) -> str:
        text = self.structure_panel.get_selected_source_text().strip()
        if text:
            return text
        text = self.translated_reader.get_selected_source_text().strip()
        if text:
            return text
        return self._selected_text.strip()

    def get_current_page_translated_text(self) -> str:
        return self.translated_reader.get_current_page_translated_text()

    def jump_to_page(self, page_number: int) -> None:
        self.source_reader.jump_to_page(page_number)
        if self.sync_enabled and self.current_mode != self.MODE_SOURCE:
            self.translated_reader.jump_to_page(page_number)

    def set_zoom_preset(self, preset_text: str) -> None:
        self.source_reader.set_zoom_preset(preset_text)

    def zoom_in(self) -> None:
        self.source_reader.zoom_in()

    def zoom_out(self) -> None:
        self.source_reader.zoom_out()

    def set_mode(self, mode: str) -> None:
        self.current_mode = mode
        if mode == self.MODE_SOURCE:
            self.source_shell.show()
            self.translated_shell.hide()
        elif mode == self.MODE_TRANSLATED:
            self.source_shell.hide()
            self.translated_shell.show()
            self.translated_stack.setCurrentIndex(0)
        elif mode == self.MODE_STRUCTURE:
            self.source_shell.show()
            self.translated_shell.show()
            self.translated_stack.setCurrentIndex(1)
            self.structure_panel.set_view_mode("table")
        else:
            self.source_shell.show()
            self.translated_shell.show()
            self.translated_stack.setCurrentIndex(0)
            self.splitter.setSizes([980, 980])

    def set_sync_enabled(self, enabled: bool) -> None:
        self.sync_enabled = bool(enabled)

    def _on_source_page_changed(self, page_number: int) -> None:
        if self.sync_enabled and self.current_mode != self.MODE_SOURCE:
            self.translated_reader.jump_to_page(page_number)
        self.current_page_changed.emit(page_number)

    def _on_translated_page_changed(self, page_number: int) -> None:
        if self.sync_enabled and self.current_mode == self.MODE_TRANSLATED:
            self.source_reader.jump_to_page(page_number)
        _ = page_number

    def _on_selected_text_changed(self, text: str) -> None:
        self._selected_text = text or ""
        self.selected_text_changed.emit(self._selected_text)

    def _on_source_page_anchor_changed(self, page_number: int, ratio: float) -> None:
        if self.sync_enabled and self.current_mode != self.MODE_SOURCE:
            self.translated_reader.jump_to_anchor(page_number, ratio)
