from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import apply_elevation, material_icon


class _ChatBubble(QFrame):
    def __init__(self, role: str, content: str, parent=None):
        super().__init__(parent)
        self.role = role
        self.content = content
        self._build_ui()

    def _build_ui(self) -> None:
        self.setObjectName("chatBubbleUser" if self.role == "user" else "chatBubbleAI")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        title = QLabel("我" if self.role == "user" else "DeepSeek")
        title.setObjectName("chatBubbleTitle")

        body = QLabel(self.content)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        action_row = QHBoxLayout()
        copy_btn = QPushButton("复制")
        copy_btn.setObjectName("ChipButton")
        copy_btn.setIcon(material_icon("copy"))
        action_row.addWidget(copy_btn)
        action_row.addStretch(1)

        copy_btn.clicked.connect(lambda: QGuiApplication.clipboard().setText(self.content))

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addLayout(action_row)


class DeepSeekChatPanel(QWidget):
    send_requested = Signal(str, str)
    clear_requested = Signal()

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

        title = QLabel("DeepSeek 聊天")
        title.setObjectName("SectionTitle")
        self.status_label = QLabel("与当前文献进行多轮问答")
        self.status_label.setObjectName("SectionSupporting")
        layout.addWidget(title)
        layout.addWidget(self.status_label)

        context_row = QHBoxLayout()
        self.context_combo = QComboBox()
        self.context_combo.addItem("当前选中文本", "selected_text")
        self.context_combo.addItem("当前页", "current_page")
        self.context_combo.addItem("当前文献全文摘要", "paper_summary")
        self.context_combo.addItem("当前文献已翻译内容", "translated_content")
        self.context_combo.addItem("自定义输入", "custom")
        context_row.addWidget(self.context_combo, 1)

        self.clear_btn = QPushButton("清空会话")
        self.clear_btn.setObjectName("ChipButton")
        self.clear_btn.setIcon(material_icon("clear"))
        context_row.addWidget(self.clear_btn)
        layout.addLayout(context_row)

        shortcuts_row1 = QHBoxLayout()
        shortcuts_row2 = QHBoxLayout()
        quick_texts = [
            "这篇文章讲了什么？",
            "本页主要内容是什么？",
            "这一段在说什么？",
            "这篇文章的创新点是什么？",
            "这篇文章的局限性是什么？",
            "适合把这篇文章引用到论文哪一部分？",
            "帮我提炼成论文可引用语句",
        ]

        for idx, text in enumerate(quick_texts):
            btn = QPushButton(text)
            btn.setObjectName("ChipButton")
            btn.clicked.connect(lambda _, t=text: self._quick_send(t))
            if idx < 4:
                shortcuts_row1.addWidget(btn)
            else:
                shortcuts_row2.addWidget(btn)

        layout.addLayout(shortcuts_row1)
        layout.addLayout(shortcuts_row2)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(0, 0, 0, 0)
        self.chat_layout.setSpacing(8)
        self.chat_layout.addStretch(1)
        self.scroll.setWidget(self.chat_container)

        self.empty_state = QLabel("开始提问吧：你可以选择“当前页”或“选中文本”作为上下文。")
        self.empty_state.setObjectName("EmptyState")
        self.empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.scroll, 1)
        layout.addWidget(self.empty_state)

        input_row = QHBoxLayout()
        self.input_edit = QPlainTextEdit()
        self.input_edit.setPlaceholderText("输入你想询问的问题...")
        self.input_edit.setFixedHeight(88)

        right_col = QVBoxLayout()
        self.send_btn = QPushButton("发送")
        self.send_btn.setObjectName("AppBarButton")
        self.send_btn.setIcon(material_icon("send"))
        self.stop_hint = QLabel("")
        self.stop_hint.setObjectName("SectionSupporting")
        self.stop_hint.setWordWrap(True)
        right_col.addWidget(self.send_btn)
        right_col.addWidget(self.stop_hint)
        right_col.addStretch(1)

        input_row.addWidget(self.input_edit, 1)
        input_row.addLayout(right_col)
        layout.addLayout(input_row)

        root.addWidget(pane)

        self.send_btn.clicked.connect(self._emit_send)
        self.clear_btn.clicked.connect(self._clear_clicked)
        self._refresh_empty_state()

    def _emit_send(self) -> None:
        text = self.input_edit.toPlainText().strip()
        if not text:
            return
        self.send_requested.emit(text, self.get_context_mode())
        self.input_edit.clear()

    def _quick_send(self, text: str) -> None:
        self.input_edit.setPlainText(text)
        self._emit_send()

    def _clear_clicked(self) -> None:
        self.clear_requested.emit()
        self.clear_messages()

    def get_context_mode(self) -> str:
        return str(self.context_combo.currentData() or "custom")

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def set_generating(self, generating: bool) -> None:
        if generating:
            self.stop_hint.setText("正在生成，请稍候...")
            self.send_btn.setEnabled(False)
        else:
            self.stop_hint.setText("")
            self.send_btn.setEnabled(True)

    def append_message(self, role: str, content: str) -> None:
        bubble = _ChatBubble(role=role, content=content)
        apply_elevation(bubble, "card")
        wrapper = QWidget()
        line = QHBoxLayout(wrapper)
        line.setContentsMargins(0, 0, 0, 0)
        if role == "user":
            line.addStretch(1)
            line.addWidget(bubble, 0)
        else:
            line.addWidget(bubble, 0)
            line.addStretch(1)

        self.chat_layout.insertWidget(self.chat_layout.count() - 1, wrapper)
        QGuiApplication.processEvents()
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
        self._refresh_empty_state()

    def clear_messages(self) -> None:
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._refresh_empty_state()

    def load_messages(self, messages: list[dict[str, str]]) -> None:
        self.clear_messages()
        for msg in messages:
            role = msg.get("role", "assistant")
            content = msg.get("content", "")
            if content.strip():
                self.append_message(role, content)
        self._refresh_empty_state()

    def set_input_text(self, text: str) -> None:
        self.input_edit.setPlainText(text or "")

    def _refresh_empty_state(self) -> None:
        has_messages = self.chat_layout.count() > 1
        self.empty_state.setVisible(not has_messages)
        self.scroll.setVisible(has_messages)

