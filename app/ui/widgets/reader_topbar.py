from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import apply_elevation, material_icon


class ReaderTopBar(QWidget):
    import_file_clicked = Signal()
    import_folder_clicked = Signal()
    search_changed = Signal(str)
    mode_changed = Signal(str)
    translate_page_clicked = Signal()
    translate_visible_clicked = Signal()
    zoom_preset_changed = Signal(str)
    zoom_in_clicked = Signal()
    zoom_out_clicked = Signal()
    page_jump_requested = Signal(int)
    ai_sidebar_toggle_clicked = Signal()
    sync_toggled = Signal(bool)
    settings_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(0)

        card = QFrame()
        card.setObjectName("TopAppBar")
        apply_elevation(card, "top_bar")

        row = QHBoxLayout(card)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(8)

        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        title = QLabel("文献阅读器")
        title.setObjectName("AppTitle")
        title_col.addWidget(title)

        self.import_btn = QToolButton()
        self.import_btn.setText("导入")
        self.import_btn.setObjectName("AppBarButton")
        self.import_btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.import_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.import_btn.setIcon(material_icon("import_file"))

        import_menu = QMenu(self.import_btn)
        import_file_action = QAction(material_icon("import_file"), "导入文件", self)
        import_folder_action = QAction(material_icon("import_folder"), "导入文件夹", self)
        import_file_action.triggered.connect(self.import_file_clicked.emit)
        import_folder_action.triggered.connect(self.import_folder_clicked.emit)
        import_menu.addAction(import_file_action)
        import_menu.addAction(import_folder_action)
        self.import_btn.setMenu(import_menu)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("TopSearchInput")
        self.search_input.setPlaceholderText("搜索文献、作者或关键词")
        self.search_input.setMinimumWidth(300)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("对照阅读", "parallel")
        self.mode_combo.addItem("仅原文", "source_only")
        self.mode_combo.addItem("仅译文", "translated_only")
        self.mode_combo.addItem("结构模式", "structure")

        self.translate_page_btn = QPushButton("翻译当前页")
        self.translate_page_btn.setObjectName("AppBarButton")
        self.translate_page_btn.setIcon(material_icon("translate"))
        self.translate_visible_btn = QPushButton("翻译可视区")
        self.translate_visible_btn.setObjectName("AppBarButton")
        self.translate_visible_btn.setIcon(material_icon("visible"))

        self.zoom_combo = QComboBox()
        self.zoom_combo.addItems(["适合宽度", "100%", "125%", "150%"])
        self.zoom_combo.setCurrentText("适合宽度")
        self.zoom_out_btn = QPushButton("")
        self.zoom_out_btn.setObjectName("AppBarButton")
        self.zoom_out_btn.setIcon(material_icon("zoom_out"))
        self.zoom_in_btn = QPushButton("")
        self.zoom_in_btn.setObjectName("AppBarButton")
        self.zoom_in_btn.setIcon(material_icon("zoom_in"))

        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.setMaximum(1)
        self.page_spin.setMinimumWidth(70)
        self.page_label = QLabel("/ 0")
        self.page_label.setObjectName("ReaderMetaLabel")

        self.sync_check = QCheckBox("同步滚动")
        self.sync_check.setChecked(True)

        self.ai_toggle_btn = QPushButton("AI")
        self.ai_toggle_btn.setObjectName("AppBarButton")
        self.ai_toggle_btn.setIcon(material_icon("chat"))

        self.settings_btn = QPushButton("")
        self.settings_btn.setObjectName("AppBarButton")
        self.settings_btn.setIcon(material_icon("settings"))
        self.settings_btn.setToolTip("设置")

        row.addLayout(title_col)
        row.addSpacing(6)
        row.addWidget(self.import_btn)
        row.addWidget(self.search_input, 1)
        row.addWidget(self.mode_combo)
        row.addWidget(self.translate_page_btn)
        row.addWidget(self.translate_visible_btn)
        row.addWidget(self.zoom_out_btn)
        row.addWidget(self.zoom_combo)
        row.addWidget(self.zoom_in_btn)
        row.addWidget(self.page_spin)
        row.addWidget(self.page_label)
        row.addWidget(self.sync_check)
        row.addWidget(self.ai_toggle_btn)
        row.addWidget(self.settings_btn)

        root.addWidget(card)

        self.search_input.textChanged.connect(self.search_changed.emit)
        self.import_btn.clicked.connect(self.import_file_clicked.emit)
        self.mode_combo.currentIndexChanged.connect(self._emit_mode_changed)
        self.translate_page_btn.clicked.connect(self.translate_page_clicked.emit)
        self.translate_visible_btn.clicked.connect(self.translate_visible_clicked.emit)
        self.zoom_combo.currentTextChanged.connect(self.zoom_preset_changed.emit)
        self.zoom_in_btn.clicked.connect(self.zoom_in_clicked.emit)
        self.zoom_out_btn.clicked.connect(self.zoom_out_clicked.emit)
        self.page_spin.valueChanged.connect(lambda value: self.page_jump_requested.emit(value - 1))
        self.sync_check.toggled.connect(self.sync_toggled.emit)
        self.ai_toggle_btn.clicked.connect(self.ai_sidebar_toggle_clicked.emit)
        self.settings_btn.clicked.connect(self.settings_clicked.emit)

    def _emit_mode_changed(self) -> None:
        self.mode_changed.emit(str(self.mode_combo.currentData() or "parallel"))

    def set_page_info(self, current_page: int, page_count: int) -> None:
        self.page_spin.blockSignals(True)
        self.page_spin.setMaximum(max(1, page_count))
        self.page_spin.setValue(max(1, current_page + 1))
        self.page_spin.blockSignals(False)
        self.page_label.setText(f"/ {page_count}")

    def set_search_text(self, text: str) -> None:
        self.search_input.blockSignals(True)
        self.search_input.setText(text)
        self.search_input.blockSignals(False)

    def set_mode(self, mode: str) -> None:
        for idx in range(self.mode_combo.count()):
            if str(self.mode_combo.itemData(idx)) == mode:
                self.mode_combo.blockSignals(True)
                self.mode_combo.setCurrentIndex(idx)
                self.mode_combo.blockSignals(False)
                return

    def set_button_enabled(self, key: str, enabled: bool) -> None:
        mapping = {
            "translate": self.translate_page_btn,
            "visible": self.translate_visible_btn,
        }
        button = mapping.get(key)
        if button is not None:
            button.setEnabled(enabled)
