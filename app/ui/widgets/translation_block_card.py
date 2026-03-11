from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from app.models.translation_page import TranslationBlockView
from app.ui.theme import apply_elevation, material_icon


class TranslationBlockCard(QFrame):
    source_selected = Signal(str)

    def __init__(self, block: TranslationBlockView, parent=None):
        super().__init__(parent)
        self.block = block
        self.setObjectName("translationBlockCard")
        self.setProperty("blockType", block.block_type)
        apply_elevation(self, "card")
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)

        title = QLabel(self.block.title)
        title.setObjectName("translationBlockTitle")

        self.translated_label = QLabel(self.block.translated_text)
        self.translated_label.setWordWrap(True)
        self.translated_label.setObjectName("translationBlockText")
        self.translated_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        source = QLabel(self.block.source_text)
        source.setWordWrap(True)
        source.setObjectName("translationBlockSource")
        source.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        action_row = QHBoxLayout()
        copy_translated_btn = QPushButton("复制译文")
        copy_translated_btn.setObjectName("ChipButton")
        copy_translated_btn.setIcon(material_icon("copy"))
        copy_source_btn = QPushButton("复制原文")
        copy_source_btn.setObjectName("ChipButton")
        copy_source_btn.setIcon(material_icon("copy"))
        action_row.addWidget(copy_translated_btn)
        action_row.addWidget(copy_source_btn)
        action_row.addStretch(1)

        copy_translated_btn.clicked.connect(
            lambda: QGuiApplication.clipboard().setText(self.block.translated_text)
        )
        copy_source_btn.clicked.connect(lambda: QGuiApplication.clipboard().setText(self.block.source_text))

        layout.addWidget(title)
        layout.addWidget(self.translated_label)
        layout.addWidget(source)
        layout.addLayout(action_row)

    def update_translated_text(self, text: str) -> None:
        self.block.translated_text = text
        self.translated_label.setText(text)

    def mousePressEvent(self, event) -> None:
        self.source_selected.emit(self.block.source_text)
        super().mousePressEvent(event)
