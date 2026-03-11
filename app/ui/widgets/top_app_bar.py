from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import apply_elevation, material_icon


class TopAppBar(QWidget):
    action_triggered = Signal(str)
    search_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buttons: dict[str, QPushButton] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(0)

        card = QFrame()
        card.setObjectName("TopAppBar")
        apply_elevation(card, "top_bar")

        root = QHBoxLayout(card)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("Paper Reader")
        title.setObjectName("AppTitle")
        subtitle = QLabel("Material 3 Desktop Reading Workspace")
        subtitle.setObjectName("AppSubtitle")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)

        root.addLayout(title_col)
        root.addSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("TopSearchInput")
        self.search_input.setPlaceholderText("搜索文献 / 作者 / 关键词")
        root.addWidget(self.search_input, 1)

        root.addSpacing(8)
        self._add_button(root, "import_file", "导入")
        self._add_button(root, "import_folder", "文件夹")
        self._add_button(root, "translate", "翻译页")
        self._add_button(root, "visible", "翻译可视")
        self._add_button(root, "translate_selected", "翻译选中")
        self._add_button(root, "explain", "解释选中")
        self._add_button(root, "summary", "全文摘要")
        self._add_button(root, "chat", "发送聊天")
        self._add_button(root, "citation", "引用")
        self._add_button(root, "logs", "日志")
        self._add_button(root, "settings", "设置")

        outer.addWidget(card)
        self.search_input.textChanged.connect(self.search_changed.emit)

    def _add_button(self, layout: QHBoxLayout, key: str, text: str) -> None:
        btn = QPushButton(text)
        btn.setObjectName("AppBarButton")
        btn.setIcon(material_icon(key))
        btn.clicked.connect(lambda: self.action_triggered.emit(key))
        layout.addWidget(btn)
        self._buttons[key] = btn

    def set_button_enabled(self, key: str, enabled: bool) -> None:
        btn = self._buttons.get(key)
        if btn:
            btn.setEnabled(enabled)

    def set_search_text(self, text: str) -> None:
        self.search_input.blockSignals(True)
        self.search_input.setText(text)
        self.search_input.blockSignals(False)
