from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import apply_elevation, material_icon


@dataclass(slots=True)
class _PaperViewItem:
    paper_id: int
    title: str
    subtitle: str
    chip: str


class _PaperCardWidget(QWidget):
    def __init__(self, item: _PaperViewItem, active: bool = False, parent=None):
        super().__init__(parent)
        self.item = item
        self.active = active
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("PaperListCard")
        card.setProperty("active", self.active)
        apply_elevation(card, "card")

        content = QVBoxLayout(card)
        content.setContentsMargins(12, 12, 12, 12)
        content.setSpacing(6)

        title = QLabel(self.item.title)
        title.setObjectName("PaperCardTitle")
        title.setWordWrap(True)

        meta = QLabel(self.item.subtitle or "暂无作者或年份信息")
        meta.setObjectName("PaperCardMeta")
        meta.setWordWrap(True)

        chip_row = QHBoxLayout()
        chip_row.setContentsMargins(0, 0, 0, 0)
        chip = QLabel(self.item.chip)
        chip.setObjectName("PaperCardChip")
        chip_row.addWidget(chip)
        chip_row.addStretch(1)

        content.addWidget(title)
        content.addWidget(meta)
        content.addLayout(chip_row)

        root.addWidget(card)


class PaperLibraryPanel(QWidget):
    search_changed = Signal(str)
    paper_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        panel = QFrame()
        panel.setObjectName("PaneSurface")
        apply_elevation(panel, "card")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("文献库")
        title.setObjectName("SectionTitle")

        subtitle = QLabel("搜索标题、作者与关键词，恢复上次阅读位置。")
        subtitle.setObjectName("SectionSupporting")

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        search_icon = QLabel()
        search_icon.setPixmap(material_icon("search").pixmap(16, 16))

        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("LibrarySearchInput")
        self.search_edit.setPlaceholderText("搜索文献")
        search_row.addWidget(search_icon)
        search_row.addWidget(self.search_edit, 1)

        self.paper_list = QListWidget()
        self.paper_list.setObjectName("PaperList")
        self.paper_list.setSpacing(6)

        self.empty_state = QLabel("文献库为空。先导入 PDF，阅读器会自动建立本地文献库。")
        self.empty_state.setObjectName("EmptyState")
        self.empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(search_row)
        layout.addWidget(self.paper_list, 1)
        layout.addWidget(self.empty_state)

        root.addWidget(panel)

        self.search_edit.textChanged.connect(self.search_changed.emit)
        self.paper_list.itemSelectionChanged.connect(self._on_selected)
        self._refresh_empty_state()

    def set_papers(self, papers: list) -> None:
        self.paper_list.clear()
        for paper in papers:
            view_item = _PaperViewItem(
                paper_id=int(paper.id),
                title=paper.display_name_cn or paper.title_cn or paper.title or paper.original_filename,
                subtitle=" | ".join(
                    [part for part in [paper.year, (paper.authors or "").strip()[:80]] if (part or "").strip()]
                ),
                chip=paper.category or "未分类",
            )
            list_item = QListWidgetItem()
            list_item.setData(Qt.ItemDataRole.UserRole, view_item.paper_id)
            card = _PaperCardWidget(view_item, active=False)
            list_item.setSizeHint(card.sizeHint())
            self.paper_list.addItem(list_item)
            self.paper_list.setItemWidget(list_item, card)
        self._refresh_empty_state()

    def select_paper(self, paper_id: int) -> None:
        for row in range(self.paper_list.count()):
            item = self.paper_list.item(row)
            if item and int(item.data(Qt.ItemDataRole.UserRole)) == int(paper_id):
                self.paper_list.setCurrentItem(item)
                return

    def _on_selected(self) -> None:
        for row in range(self.paper_list.count()):
            item = self.paper_list.item(row)
            widget = self.paper_list.itemWidget(item)
            if widget is None:
                continue
            is_active = item == self.paper_list.currentItem()
            card = widget.findChild(QFrame, "PaperListCard")
            if card is not None:
                card.setProperty("active", is_active)
                card.style().unpolish(card)
                card.style().polish(card)
        item = self.paper_list.currentItem()
        if item:
            self.paper_selected.emit(int(item.data(Qt.ItemDataRole.UserRole)))

    def _refresh_empty_state(self) -> None:
        is_empty = self.paper_list.count() == 0
        self.paper_list.setVisible(not is_empty)
        self.empty_state.setVisible(is_empty)
