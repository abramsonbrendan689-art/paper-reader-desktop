from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models.paper import PaperBlock
from app.services.translation_service import TranslationResult
from app.ui.theme import apply_elevation, material_icon


@dataclass(slots=True)
class _CardRef:
    root: QFrame
    source_label: QLabel
    target_label: QLabel


class TranslationPanel(QWidget):
    selected_text_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._blocks: list[PaperBlock] = []
        self._results_by_index: dict[int, TranslationResult] = {}
        self._cards: dict[int, _CardRef] = {}
        self._selected_source_text = ""
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        pane = QFrame()
        pane.setObjectName("PaneSurface")
        apply_elevation(pane, "card")

        layout = QVBoxLayout(pane)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(8)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("翻译对照")
        title.setObjectName("SectionTitle")
        self.status_label = QLabel("翻译状态：未加载")
        self.status_label.setObjectName("SectionSupporting")
        title_col.addWidget(title)
        title_col.addWidget(self.status_label)

        self.table_mode_btn = QPushButton("表格模式")
        self.table_mode_btn.setObjectName("SegmentButton")
        self.table_mode_btn.setCheckable(True)

        self.read_mode_btn = QPushButton("阅读模式")
        self.read_mode_btn.setObjectName("SegmentButton")
        self.read_mode_btn.setCheckable(True)
        self.read_mode_btn.setChecked(True)

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.mode_group.addButton(self.table_mode_btn)
        self.mode_group.addButton(self.read_mode_btn)

        self.copy_btn = QPushButton("复制选中文本")
        self.copy_btn.setIcon(material_icon("copy"))
        self.copy_btn.setObjectName("ChipButton")

        header.addLayout(title_col, 1)
        header.addWidget(self.table_mode_btn)
        header.addWidget(self.read_mode_btn)
        header.addWidget(self.copy_btn)
        layout.addLayout(header)

        self.stacked = QStackedWidget()
        layout.addWidget(self.stacked, 1)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Block", "类型", "原文", "中文翻译"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.stacked.addWidget(self.table)

        self.read_scroll = QScrollArea()
        self.read_scroll.setWidgetResizable(True)
        self.read_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.read_container = QWidget()
        self.read_layout = QVBoxLayout(self.read_container)
        self.read_layout.setContentsMargins(0, 0, 0, 0)
        self.read_layout.setSpacing(10)
        self.read_layout.addStretch(1)
        self.read_scroll.setWidget(self.read_container)
        self.stacked.addWidget(self.read_scroll)

        self.empty_state = QLabel("当前页暂无翻译内容。可点击“翻译当前页”或“翻译可视区域”。")
        self.empty_state.setObjectName("EmptyState")
        self.empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty_state)

        root.addWidget(pane)

        self.table_mode_btn.clicked.connect(lambda: self.stacked.setCurrentIndex(0))
        self.read_mode_btn.clicked.connect(lambda: self.stacked.setCurrentIndex(1))
        self.table.itemSelectionChanged.connect(self._emit_selected_source)
        self.copy_btn.clicked.connect(self._copy_selected)
        self.stacked.setCurrentIndex(1)
        self._refresh_empty_state()

    def set_view_mode(self, mode: str) -> None:
        if mode == "table":
            self.table_mode_btn.setChecked(True)
            self.stacked.setCurrentIndex(0)
        else:
            self.read_mode_btn.setChecked(True)
            self.stacked.setCurrentIndex(1)

    def set_loading(self, text: str) -> None:
        self.status_label.setText(text)

    def show_block_source_only(self, blocks: Iterable[PaperBlock]) -> None:
        self._blocks = list(blocks)
        self._results_by_index = {}
        self._selected_source_text = ""

        self.table.setRowCount(len(self._blocks))
        for row, block in enumerate(self._blocks):
            self._set_table_row(row=row, block=block, translated_text="（未翻译）")

        self._rebuild_read_cards()
        self.status_label.setText(f"翻译状态：当前页共 {len(self._blocks)} 个文本块")
        self._refresh_empty_state()

    def show_translations(
        self,
        blocks: list[PaperBlock],
        translation_results: list[TranslationResult],
    ) -> None:
        self._blocks = list(blocks)
        self._results_by_index = {x.block_index: x for x in translation_results}

        self.table.setRowCount(len(self._blocks))
        cache_count = 0
        for row, block in enumerate(self._blocks):
            result = self._results_by_index.get(block.block_index)
            translated_text = result.translated_text if result else "（未翻译）"
            if result and result.from_cache:
                cache_count += 1
            self._set_table_row(row, block, translated_text)

        self._rebuild_read_cards()
        self.status_label.setText(f"翻译状态：共 {len(self._blocks)} 个块，缓存命中 {cache_count} 个")
        self._refresh_empty_state()

    def update_translation_result(self, result: TranslationResult) -> None:
        self._results_by_index[result.block_index] = result
        row = self._find_row_by_block_index(result.block_index)
        if row >= 0:
            item = self.table.item(row, 3)
            if item:
                item.setText(result.translated_text)

        card = self._cards.get(result.block_index)
        if card:
            card.target_label.setText(result.translated_text)
        self._refresh_empty_state()

    def get_selected_source_text(self) -> str:
        row = self.table.currentRow()
        if row >= 0:
            item = self.table.item(row, 2)
            if item:
                return item.text().strip()
        return self._selected_source_text.strip()

    def get_current_page_translated_text(self) -> str:
        texts: list[str] = []
        for block in self._blocks:
            result = self._results_by_index.get(block.block_index)
            if result and result.translated_text.strip():
                texts.append(result.translated_text.strip())
        return "\n".join(texts)

    def _find_row_by_block_index(self, block_index: int) -> int:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if not item:
                continue
            try:
                if int(item.text()) == block_index:
                    return row
            except Exception:  # noqa: BLE001
                continue
        return -1

    def _set_table_row(self, row: int, block: PaperBlock, translated_text: str) -> None:
        self.table.setItem(row, 0, QTableWidgetItem(str(block.block_index)))
        self.table.setItem(row, 1, QTableWidgetItem(block.block_type))
        source_item = QTableWidgetItem(block.text)
        source_item.setTextAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        translated_item = QTableWidgetItem(translated_text)
        translated_item.setTextAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.table.setItem(row, 2, source_item)
        self.table.setItem(row, 3, translated_item)

    def _clear_read_cards(self) -> None:
        while self.read_layout.count() > 1:
            item = self.read_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._cards.clear()

    def _rebuild_read_cards(self) -> None:
        self._clear_read_cards()
        for block in self._blocks:
            result = self._results_by_index.get(block.block_index)
            translated = result.translated_text if result else "（未翻译）"

            card = QFrame()
            card.setObjectName("translationCard")
            card.setProperty("blockType", block.block_type)
            apply_elevation(card, "card")

            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 12, 12, 12)
            card_layout.setSpacing(6)

            block_meta = QLabel(f"Block {block.block_index} · {block.block_type}")
            block_meta.setObjectName("translationCardMeta")

            source_title = QLabel("原文")
            source_title.setObjectName("translationCardTitle")
            source_label = QLabel(block.text)
            source_label.setWordWrap(True)
            source_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

            target_title = QLabel("中文翻译")
            target_title.setObjectName("translationCardTitle")
            target_label = QLabel(translated)
            target_label.setWordWrap(True)
            target_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

            action_row = QHBoxLayout()
            copy_source_btn = QPushButton("复制原文")
            copy_source_btn.setObjectName("ChipButton")
            copy_source_btn.setIcon(material_icon("copy"))
            copy_target_btn = QPushButton("复制译文")
            copy_target_btn.setObjectName("ChipButton")
            copy_target_btn.setIcon(material_icon("copy"))
            action_row.addWidget(copy_source_btn)
            action_row.addWidget(copy_target_btn)
            action_row.addStretch(1)

            copy_source_btn.clicked.connect(
                lambda _, lbl=source_label: QGuiApplication.clipboard().setText(lbl.text())
            )
            copy_target_btn.clicked.connect(
                lambda _, lbl=target_label: QGuiApplication.clipboard().setText(lbl.text())
            )
            card.mousePressEvent = self._make_card_click_handler(block.text)  # type: ignore[method-assign]

            card_layout.addWidget(block_meta)
            card_layout.addWidget(source_title)
            card_layout.addWidget(source_label)
            card_layout.addWidget(target_title)
            card_layout.addWidget(target_label)
            card_layout.addLayout(action_row)

            self.read_layout.insertWidget(self.read_layout.count() - 1, card)
            self._cards[block.block_index] = _CardRef(root=card, source_label=source_label, target_label=target_label)

    def _make_card_click_handler(self, source_text: str):
        def handler(event):
            self._selected_source_text = source_text
            self.selected_text_changed.emit(source_text)
            event.accept()

        return handler

    def _emit_selected_source(self) -> None:
        text = self.get_selected_source_text()
        self._selected_source_text = text
        self.selected_text_changed.emit(text)

    def _copy_selected(self) -> None:
        text = self.get_selected_source_text()
        if text:
            QGuiApplication.clipboard().setText(text)

    def _refresh_empty_state(self) -> None:
        has_data = len(self._blocks) > 0
        self.empty_state.setVisible(not has_data)
        self.stacked.setVisible(has_data)
