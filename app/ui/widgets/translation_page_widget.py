from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from app.models.translation_page import TranslationBlockView, TranslationPageView
from app.ui.theme import apply_elevation
from app.ui.widgets.translation_block_card import TranslationBlockCard


class TranslationPageWidget(QFrame):
    source_selected = Signal(str)

    def __init__(self, page: TranslationPageView, parent=None):
        super().__init__(parent)
        self.page = page
        self.block_cards: dict[int, TranslationBlockCard] = {}
        self.setObjectName("translatedPageCard")
        apply_elevation(self, "card")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header_row = QHBoxLayout()
        title = QLabel(self.page.heading or f"译文第 {self.page.page_number + 1} 页")
        title.setObjectName("translatedPageTitle")
        meta = QLabel(self.page.meta)
        meta.setObjectName("translatedPageMeta")
        header_row.addWidget(title)
        header_row.addStretch(1)
        header_row.addWidget(meta)

        layout.addLayout(header_row)
        self.blocks_container = QVBoxLayout()
        self.blocks_container.setContentsMargins(0, 0, 0, 0)
        self.blocks_container.setSpacing(8)
        layout.addLayout(self.blocks_container, 1)
        layout.addStretch(1)

        self._rebuild_blocks(self.page.blocks)

    def _clear_blocks(self) -> None:
        while self.blocks_container.count():
            item = self.blocks_container.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.block_cards.clear()

    def _rebuild_blocks(self, blocks: list[TranslationBlockView]) -> None:
        self._clear_blocks()
        if not blocks:
            empty = QLabel("本页暂无可显示译文块。")
            empty.setObjectName("EmptyState")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.blocks_container.addWidget(empty)
            return

        for block in blocks:
            card = TranslationBlockCard(block)
            card.source_selected.connect(self.source_selected.emit)
            self.blocks_container.addWidget(card)
            self.block_cards[block.block_index] = card

    def set_page(self, page: TranslationPageView) -> None:
        self.page = page
        self._rebuild_blocks(page.blocks)

    def update_block_text(self, block_index: int, translated_text: str) -> None:
        card = self.block_cards.get(block_index)
        if card:
            card.update_translated_text(translated_text)

