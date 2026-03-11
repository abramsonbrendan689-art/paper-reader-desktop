from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import apply_elevation, material_icon


class AIReadingPanel(QWidget):
    action_requested = Signal(str)
    save_note_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
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

        title = QLabel("AI 阅读")
        title.setObjectName("SectionTitle")
        self.status_label = QLabel("AI 阅读助手就绪")
        self.status_label.setObjectName("SectionSupporting")
        layout.addWidget(title)
        layout.addWidget(self.status_label)

        btn_grid = QGridLayout()
        btn_grid.setHorizontalSpacing(8)
        btn_grid.setVerticalSpacing(8)

        self.page_summary_btn = self._action_btn("当前页摘要", "summary", "page")
        self.paper_summary_btn = self._action_btn("全文摘要", "summary", "paper")
        self.innovation_btn = self._action_btn("创新点", "summary", "innovation")
        self.limitation_btn = self._action_btn("局限性", "summary", "limitation")
        self.method_btn = self._action_btn("方法总结", "summary", "method")
        self.conclusion_btn = self._action_btn("结论总结", "summary", "conclusion")
        self.reading_note_btn = self._action_btn("阅读笔记", "notes", "reading_note")
        self.clear_btn = QPushButton("清空结果")
        self.clear_btn.setObjectName("ChipButton")
        self.clear_btn.setIcon(material_icon("clear"))

        buttons = [
            self.page_summary_btn,
            self.paper_summary_btn,
            self.innovation_btn,
            self.limitation_btn,
            self.method_btn,
            self.conclusion_btn,
            self.reading_note_btn,
            self.clear_btn,
        ]
        positions = [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0), (2, 1), (3, 0), (3, 1)]
        for btn, (r, c) in zip(buttons, positions):
            btn_grid.addWidget(btn, r, c)

        layout.addLayout(btn_grid)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(10)
        self.container_layout.addStretch(1)
        self.scroll.setWidget(self.container)

        self.empty_state = QLabel("点击上方能力按钮，生成结构化阅读结果卡片。")
        self.empty_state.setObjectName("EmptyState")
        self.empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.scroll, 1)
        layout.addWidget(self.empty_state)
        root.addWidget(pane)

        self.clear_btn.clicked.connect(self.clear_results)
        self._refresh_empty_state()

    def _action_btn(self, text: str, icon_name: str, action: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("ChipButton")
        btn.setIcon(material_icon(icon_name))
        btn.clicked.connect(lambda: self.action_requested.emit(action))
        return btn

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def add_result_card(self, title: str, content: str) -> None:
        card = QFrame()
        card.setObjectName("aiResultCard")
        apply_elevation(card, "card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("aiResultTitle")

        ai_chip = QLabel("AI 生成内容")
        ai_chip.setObjectName("AiGeneratedChip")

        content_label = QLabel(content)
        content_label.setWordWrap(True)
        content_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        action_row = QHBoxLayout()
        copy_btn = QPushButton("复制")
        copy_btn.setObjectName("ChipButton")
        copy_btn.setIcon(material_icon("copy"))
        save_btn = QPushButton("保存到笔记")
        save_btn.setObjectName("ChipButton")
        save_btn.setIcon(material_icon("notes"))
        action_row.addWidget(copy_btn)
        action_row.addWidget(save_btn)
        action_row.addStretch(1)

        copy_btn.clicked.connect(lambda: QGuiApplication.clipboard().setText(content))
        save_btn.clicked.connect(lambda: self.save_note_requested.emit(content))

        layout.addWidget(title_label)
        layout.addWidget(ai_chip)
        layout.addWidget(content_label)
        layout.addLayout(action_row)

        self.container_layout.insertWidget(self.container_layout.count() - 1, card)
        self._refresh_empty_state()

    def clear_results(self) -> None:
        while self.container_layout.count() > 1:
            item = self.container_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.set_status("结果已清空")
        self._refresh_empty_state()

    def _refresh_empty_state(self) -> None:
        has_results = self.container_layout.count() > 1
        self.scroll.setVisible(has_results)
        self.empty_state.setVisible(not has_results)

