from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QCheckBox, QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from app.ui.theme import apply_elevation, material_icon


class ReaderToolbar(QWidget):
    mode_changed = Signal(str)
    sync_toggled = Signal(bool)

    MODE_PARALLEL = "parallel"
    MODE_SOURCE = "source_only"
    MODE_TRANSLATED = "translated_only"
    MODE_STRUCTURE = "structure"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("ReaderToolbar")
        apply_elevation(card, "top_bar")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        title = QLabel("对照翻译阅读")
        title.setObjectName("SectionTitle")

        self.parallel_btn = self._mode_btn("对照模式", "parallel", True)
        self.source_btn = self._mode_btn("仅原文", "import_file", False)
        self.translated_btn = self._mode_btn("仅译文", "summary", False)
        self.structure_btn = self._mode_btn("结构模式", "notes", False)

        group = QButtonGroup(self)
        group.setExclusive(True)
        for btn in [self.parallel_btn, self.source_btn, self.translated_btn, self.structure_btn]:
            group.addButton(btn)

        self.sync_check = QCheckBox("同步滚动")
        self.sync_check.setChecked(True)

        self.source_page = QLabel("原文页：-")
        self.source_page.setObjectName("SectionSupporting")
        self.translated_page = QLabel("译文页：-")
        self.translated_page.setObjectName("SectionSupporting")

        layout.addWidget(title)
        layout.addSpacing(8)
        layout.addWidget(self.parallel_btn)
        layout.addWidget(self.source_btn)
        layout.addWidget(self.translated_btn)
        layout.addWidget(self.structure_btn)
        layout.addSpacing(8)
        layout.addWidget(self.sync_check)
        layout.addStretch(1)
        layout.addWidget(self.source_page)
        layout.addWidget(self.translated_page)
        root.addWidget(card)

        self.parallel_btn.clicked.connect(lambda: self.mode_changed.emit(self.MODE_PARALLEL))
        self.source_btn.clicked.connect(lambda: self.mode_changed.emit(self.MODE_SOURCE))
        self.translated_btn.clicked.connect(lambda: self.mode_changed.emit(self.MODE_TRANSLATED))
        self.structure_btn.clicked.connect(lambda: self.mode_changed.emit(self.MODE_STRUCTURE))
        self.sync_check.toggled.connect(self.sync_toggled.emit)

    @staticmethod
    def _mode_btn(text: str, icon_name: str, checked: bool) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("SegmentButton")
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.setIcon(material_icon(icon_name))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn

    def set_page_info(self, source_page: int, translated_page: int, page_count: int) -> None:
        if page_count <= 0:
            self.source_page.setText("原文页：-")
            self.translated_page.setText("译文页：-")
            return
        self.source_page.setText(f"原文页：{source_page + 1}/{page_count}")
        self.translated_page.setText(f"译文页：{translated_page + 1}/{page_count}")
