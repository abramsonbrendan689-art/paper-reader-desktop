from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from app.models.paper import PaperBlock
from app.models.translation_page import TranslationPageView
from app.services.translation_layout_service import TranslationLayoutService
from app.services.translation_service import TranslationResult
from app.ui.theme import apply_elevation
from app.ui.widgets.translated_page_widget import TranslatedPageWidget


class TranslatedDocumentReader(QWidget):
    current_page_changed = Signal(int)
    visible_pages_changed = Signal(list)
    scroll_ratio_changed = Signal(float)
    selected_text_changed = Signal(str)
    action_requested = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout_service = TranslationLayoutService()

        self.page_count = 0
        self.current_page = 0
        self._pages: dict[int, TranslationPageView] = {}
        self._page_widgets: dict[int, TranslatedPageWidget] = {}
        self._selected_source_text = ""
        self._sync_lock = False
        self._runtime_status: dict[int, tuple[str, str]] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.outer = QFrame()
        self.outer.setObjectName("translatedReaderOuter")
        apply_elevation(self.outer, "card")

        outer_layout = QVBoxLayout(self.outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(18, 24, 18, 28)
        self.container_layout.setSpacing(28)
        self.container_layout.addStretch(1)
        self.scroll.setWidget(self.container)

        self.empty_state = QLabel("译文阅读区：请先翻译当前页或翻译可视区。")
        self.empty_state.setObjectName("EmptyState")
        self.empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)

        outer_layout.addWidget(self.scroll, 1)
        outer_layout.addWidget(self.empty_state)
        root.addWidget(self.outer)

        self.scroll.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)
        self._refresh_empty_state()

    def clear_document(self) -> None:
        self.page_count = 0
        self.current_page = 0
        self._pages.clear()
        while self.container_layout.count() > 1:
            item = self.container_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._page_widgets.clear()
        self._runtime_status.clear()
        self._refresh_empty_state()

    def initialize_document(self, page_count: int) -> None:
        self.clear_document()
        self.page_count = max(0, int(page_count))
        for idx in range(self.page_count):
            view = TranslationPageView(
                page_number=idx,
                blocks=[],
                heading=f"译文第 {idx + 1} 页",
                meta="未翻译",
            )
            self._pages[idx] = view
            widget = TranslatedPageWidget(view)
            widget.source_selected.connect(self._on_source_selected)
            widget.action_requested.connect(self.action_requested.emit)
            self.container_layout.insertWidget(
                self.container_layout.count() - 1,
                widget,
                0,
                Qt.AlignmentFlag.AlignHCenter,
            )
            self._page_widgets[idx] = widget
        self._refresh_empty_state()

    def set_page_blocks(
        self,
        page_number: int,
        blocks: list[PaperBlock],
        results: list[TranslationResult] | None = None,
    ) -> None:
        if page_number not in self._page_widgets:
            return

        view = self.layout_service.build_page_view(
            page_number=page_number,
            blocks=blocks,
            results=results,
        )
        self._pages[page_number] = view

        old_widget = self._page_widgets[page_number]
        new_widget = TranslatedPageWidget(view)
        new_widget.source_selected.connect(self._on_source_selected)
        new_widget.action_requested.connect(self.action_requested.emit)
        self.container_layout.replaceWidget(old_widget, new_widget)
        old_widget.deleteLater()
        self._page_widgets[page_number] = new_widget
        runtime = self._runtime_status.get(page_number)
        if runtime:
            new_widget.set_page_status(runtime[0], runtime[1])
        self._refresh_empty_state()

    def update_block_translation(self, result: TranslationResult) -> None:
        page = self._pages.get(result.page_number)
        if page is None:
            return

        source_text = ""
        for block in page.blocks:
            if block.block_index == result.block_index:
                block.translated_text = result.translated_text
                source_text = block.source_text
                break

        widget = self._page_widgets.get(result.page_number)
        if widget is not None and source_text:
            widget.update_block_text(result.block_index, result.translated_text, source_text)
            status, status_text = self._compute_page_status(page)
            widget.set_page_status(
                status,
                status_text,
                translated_blocks=page.translated_blocks,
                total_blocks=page.total_blocks,
                failed_blocks=page.failed_blocks,
            )
            self._runtime_status[result.page_number] = (status, status_text)

    def jump_to_page(self, page_number: int) -> None:
        if not self._page_widgets:
            return
        page_number = max(0, min(page_number, self.page_count - 1))
        target = self._page_widgets.get(page_number)
        if target is None:
            return
        bar = self.scroll.verticalScrollBar()
        bar.setValue(max(0, target.y() - 20))
        self._set_current_page(page_number)

    def jump_to_anchor(self, page_number: int, ratio: float) -> None:
        if not self._page_widgets:
            return
        page_number = max(0, min(page_number, self.page_count - 1))
        page_widget = self._page_widgets.get(page_number)
        if page_widget is None:
            return
        target_widget = page_widget.get_anchor_widget_for_ratio(ratio)
        if target_widget is None:
            self.jump_to_page(page_number)
            return
        bar = self.scroll.verticalScrollBar()
        target_value = max(0, page_widget.y() + target_widget.y() - 120)
        if abs(bar.value() - target_value) > 12:
            self._sync_lock = True
            bar.setValue(target_value)
            QTimer.singleShot(80, self._release_sync_lock)
        self._set_current_page(page_number)

    def get_current_page(self) -> int:
        return self.current_page

    def get_page_count(self) -> int:
        return self.page_count

    def get_visible_page_numbers(self) -> list[int]:
        if not self._page_widgets:
            return []
        top = self.scroll.verticalScrollBar().value()
        bottom = top + self.scroll.viewport().height()
        visible: list[int] = []
        for page_number, widget in self._page_widgets.items():
            y = widget.y()
            height = widget.height()
            if y + height >= top and y <= bottom:
                visible.append(page_number)
        return sorted(visible)

    def get_scroll_ratio(self) -> float:
        bar = self.scroll.verticalScrollBar()
        return bar.value() / bar.maximum() if bar.maximum() > 0 else 0.0

    def set_scroll_ratio(self, ratio: float) -> None:
        ratio = max(0.0, min(1.0, ratio))
        bar = self.scroll.verticalScrollBar()
        if bar.maximum() <= 0:
            return
        self._sync_lock = True
        bar.setValue(int(ratio * bar.maximum()))
        QTimer.singleShot(80, self._release_sync_lock)

    def set_page_runtime_status(self, page_number: int, status: str, text: str) -> None:
        self._runtime_status[page_number] = (status, text)
        page = self._pages.get(page_number)
        widget = self._page_widgets.get(page_number)
        if page:
            page.status = status
            page.status_text = text
        if widget:
            widget.set_page_status(status, text)

    def get_selected_source_text(self) -> str:
        return self._selected_source_text.strip()

    def get_current_page_translated_text(self) -> str:
        page = self._pages.get(self.current_page)
        if page is None:
            return ""
        return "\n".join(
            block.translated_text for block in page.blocks if block.translated_text.strip()
        )

    def _release_sync_lock(self) -> None:
        self._sync_lock = False

    def _set_current_page(self, page_number: int) -> None:
        if page_number == self.current_page:
            return
        self.current_page = page_number
        self.current_page_changed.emit(page_number)

    def _on_scroll_changed(self, _value: int) -> None:
        if self._sync_lock:
            return

        if self._page_widgets:
            center_y = self.scroll.verticalScrollBar().value() + self.scroll.viewport().height() / 2
            best_page = self.current_page
            best_distance = float("inf")
            for page_number, widget in self._page_widgets.items():
                page_center = widget.y() + widget.height() / 2
                distance = abs(page_center - center_y)
                if distance < best_distance:
                    best_distance = distance
                    best_page = page_number
            self._set_current_page(best_page)

        self.visible_pages_changed.emit(self.get_visible_page_numbers())
        self.scroll_ratio_changed.emit(self.get_scroll_ratio())

    def _on_source_selected(self, text: str) -> None:
        self._selected_source_text = text or ""
        self.selected_text_changed.emit(self._selected_source_text)

    def _refresh_empty_state(self) -> None:
        has_pages = self.page_count > 0 and bool(self._page_widgets)
        self.scroll.setVisible(has_pages)
        self.empty_state.setVisible(not has_pages)

    @staticmethod
    def _compute_page_status(page: TranslationPageView) -> tuple[str, str]:
        total_blocks = 0
        translated_blocks = 0
        failed_blocks = 0
        for block in page.blocks:
            if block.block_type in {"header", "footer"} or not block.source_text.strip():
                continue
            total_blocks += 1
            text = (block.translated_text or "").strip()
            if not text:
                continue
            if text.startswith("翻译失败"):
                failed_blocks += 1
            else:
                translated_blocks += 1

        page.total_blocks = total_blocks
        page.translated_blocks = translated_blocks
        page.failed_blocks = failed_blocks

        if total_blocks <= 0:
            return "empty", "当前页未识别到可阅读文本块。"
        if translated_blocks == 0 and failed_blocks > 0:
            return "failed", f"当前页翻译失败，共 {failed_blocks} 个块失败。"
        if translated_blocks == 0:
            return "untranslated", f"当前页尚未生成译文，共 {total_blocks} 个块。"
        if translated_blocks < total_blocks:
            return "partial", f"当前页已完成 {translated_blocks}/{total_blocks} 个块。"
        return "done", f"当前页译文已完成，共 {translated_blocks} 个块。"
