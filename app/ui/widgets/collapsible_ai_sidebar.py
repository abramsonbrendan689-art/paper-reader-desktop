from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import apply_elevation, material_icon


class CollapsibleAISidebar(QWidget):
    expanded_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._expanded = False
        self._build_ui()
        self.set_expanded(False)

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self.rail = QFrame()
        self.rail.setObjectName("AiSidebarRail")
        apply_elevation(self.rail, "card")
        rail_layout = QVBoxLayout(self.rail)
        rail_layout.setContentsMargins(8, 12, 8, 12)
        rail_layout.setSpacing(8)

        self.toggle_btn = QPushButton("")
        self.toggle_btn.setObjectName("ChipButton")
        self.toggle_btn.setToolTip("展开或收起 AI 侧栏")

        self.ai_btn = QPushButton("")
        self.ai_btn.setObjectName("SegmentButton")
        self.ai_btn.setCheckable(True)
        self.ai_btn.setIcon(material_icon("summary"))
        self.ai_btn.setToolTip("AI 阅读")

        self.chat_btn = QPushButton("")
        self.chat_btn.setObjectName("SegmentButton")
        self.chat_btn.setCheckable(True)
        self.chat_btn.setIcon(material_icon("chat"))
        self.chat_btn.setToolTip("DeepSeek 聊天")

        self.note_btn = QPushButton("")
        self.note_btn.setObjectName("SegmentButton")
        self.note_btn.setCheckable(True)
        self.note_btn.setIcon(material_icon("notes"))
        self.note_btn.setToolTip("笔记")

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.mode_group.addButton(self.ai_btn, 0)
        self.mode_group.addButton(self.chat_btn, 1)
        self.mode_group.addButton(self.note_btn, 2)
        self.ai_btn.setChecked(True)

        rail_layout.addWidget(self.toggle_btn)
        rail_layout.addSpacing(8)
        rail_layout.addWidget(self.ai_btn)
        rail_layout.addWidget(self.chat_btn)
        rail_layout.addWidget(self.note_btn)
        rail_layout.addStretch(1)

        self.content = QFrame()
        self.content.setObjectName("AiSidebarContent")
        apply_elevation(self.content, "card")
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(8)

        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack, 1)

        root.addWidget(self.rail)
        root.addWidget(self.content, 1)

        self.toggle_btn.clicked.connect(self.toggle)
        self.mode_group.idClicked.connect(self.stack.setCurrentIndex)

    def set_panels(self, ai_widget: QWidget, chat_widget: QWidget, notes_widget: QWidget) -> None:
        self.stack.addWidget(ai_widget)
        self.stack.addWidget(chat_widget)
        self.stack.addWidget(notes_widget)
        self.stack.setCurrentIndex(0)

    def toggle(self) -> None:
        self.set_expanded(not self._expanded)

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = bool(expanded)
        if self._expanded:
            self.content.show()
            self.setMinimumWidth(400)
            self.setMaximumWidth(440)
            self.toggle_btn.setIcon(material_icon("next"))
        else:
            self.content.hide()
            self.setMinimumWidth(52)
            self.setMaximumWidth(52)
            self.toggle_btn.setIcon(material_icon("prev"))
        self.expanded_changed.emit(self._expanded)

    def is_expanded(self) -> bool:
        return self._expanded
