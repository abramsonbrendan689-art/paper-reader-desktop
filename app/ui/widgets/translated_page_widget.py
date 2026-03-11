from __future__ import annotations

import html
from collections import defaultdict

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QContextMenuEvent, QGuiApplication
from PySide6.QtWidgets import QFrame, QLabel, QMenu, QVBoxLayout, QWidget

from app.models.translation_page import TranslationBlockView, TranslationPageView
from app.ui.theme import apply_elevation


class _ParagraphLabel(QLabel):
    paragraph_clicked = Signal(str)
    action_requested = Signal(str, str)

    def __init__(self, source_text: str, translated_text: str, role: str, parent=None):
        super().__init__(parent)
        self.source_text = source_text
        self.translated_text = translated_text
        self.role = role
        self.setWordWrap(True)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.setCursor(Qt.CursorShape.IBeamCursor)
        self.setObjectName("translatedParagraph")
        self.setProperty("paragraphRole", role)
        self._render_text()

    def _render_text(self) -> None:
        body = html.escape(self.translated_text or "").replace("\n", "<br>")
        self.setText(f"<div style='line-height: 1.78; margin: 0 0 10px 0;'>{body}</div>")

    def set_translated_text(self, translated_text: str) -> None:
        self.translated_text = translated_text
        self._render_text()

    def mousePressEvent(self, event) -> None:
        self.paragraph_clicked.emit(self.source_text)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = QMenu(self)
        copy_translated = QAction("复制译文", self)
        copy_source = QAction("复制原文", self)
        explain_action = QAction("解释这段", self)
        chat_action = QAction("发送到聊天", self)
        note_action = QAction("加入笔记", self)
        copy_translated.triggered.connect(
            lambda: QGuiApplication.clipboard().setText(self.translated_text)
        )
        copy_source.triggered.connect(lambda: QGuiApplication.clipboard().setText(self.source_text))
        explain_action.triggered.connect(lambda: self.action_requested.emit("explain", self.source_text))
        chat_action.triggered.connect(lambda: self.action_requested.emit("chat", self.source_text))
        note_action.triggered.connect(lambda: self.action_requested.emit("note", self.source_text))
        menu.addAction(copy_translated)
        menu.addAction(copy_source)
        menu.addSeparator()
        menu.addAction(explain_action)
        menu.addAction(chat_action)
        menu.addAction(note_action)
        menu.exec(event.globalPos())


class TranslatedPageWidget(QFrame):
    source_selected = Signal(str)
    action_requested = Signal(str, str)

    def __init__(self, page: TranslationPageView, parent=None):
        super().__init__(parent)
        self.page = page
        self._paragraph_widgets: dict[int, QLabel] = {}
        self._status_banner: QFrame | None = None
        self._status_title: QLabel | None = None
        self._status_body: QLabel | None = None
        self.setObjectName("translatedPageContainer")
        apply_elevation(self, "card")
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        page_surface = QFrame()
        page_surface.setObjectName("translatedPageSurface")
        page_surface.setMinimumWidth(720)
        page_surface.setMaximumWidth(860)

        surface_layout = QVBoxLayout(page_surface)
        surface_layout.setContentsMargins(64, 66, 64, 66)
        surface_layout.setSpacing(16)

        meta = QLabel(f"译文第 {self.page.page_number + 1} 页")
        meta.setObjectName("translatedPageMeta")
        surface_layout.addWidget(meta)

        self._status_banner = QFrame()
        self._status_banner.setObjectName("translatedStatusBanner")
        self._status_banner.setProperty("status", self.page.status)
        status_layout = QVBoxLayout(self._status_banner)
        status_layout.setContentsMargins(14, 12, 14, 12)
        status_layout.setSpacing(4)
        self._status_title = QLabel()
        self._status_title.setObjectName("translatedStatusTitle")
        self._status_body = QLabel()
        self._status_body.setObjectName("translatedStatusBody")
        self._status_body.setWordWrap(True)
        status_layout.addWidget(self._status_title)
        status_layout.addWidget(self._status_body)
        surface_layout.addWidget(self._status_banner)
        self._apply_page_status()

        title_text = self._pick_title()
        if title_text:
            title_label = QLabel(title_text)
            title_label.setObjectName("translatedDocTitle")
            title_label.setWordWrap(True)
            surface_layout.addWidget(title_label)

            original_title = self._pick_original_title(title_text)
            if original_title:
                original_label = QLabel(html.escape(original_title))
                original_label.setObjectName("translatedOriginalTitle")
                original_label.setWordWrap(True)
                surface_layout.addWidget(original_label)

        meta_blocks = self._collect_meta_blocks()
        if meta_blocks:
            meta_strip = QFrame()
            meta_strip.setObjectName("translatedInfoStrip")
            meta_layout = QVBoxLayout(meta_strip)
            meta_layout.setContentsMargins(14, 12, 14, 12)
            meta_layout.setSpacing(6)
            for block in meta_blocks:
                line = QLabel(html.escape(block.translated_text))
                line.setObjectName("translatedMetaLine")
                line.setWordWrap(True)
                meta_layout.addWidget(line)
                self._paragraph_widgets[block.block_index] = self._build_hidden_ref(block)
            surface_layout.addWidget(meta_strip)

        grouped = self._group_blocks()
        self._render_section(surface_layout, "摘要", grouped["abstract"], role="abstract", boxed=True)
        self._render_section(surface_layout, "关键词", grouped["keywords"], role="keywords", boxed=True)
        self._render_body(surface_layout, grouped["body"])
        self._render_section(surface_layout, "图表说明", grouped["figure"], role="figure", boxed=False)
        self._render_section(surface_layout, "公式相关", grouped["formula"], role="formula", boxed=True)
        self._render_section(surface_layout, "参考文献", grouped["references"], role="references", boxed=False)

        if not any(grouped.values()) and not meta_blocks:
            empty = QLabel("本页暂无译文。")
            empty.setObjectName("EmptyState")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            surface_layout.addWidget(empty)

        root.addWidget(page_surface)

    def _build_hidden_ref(self, block: TranslationBlockView) -> _ParagraphLabel:
        ref = _ParagraphLabel(block.source_text, block.translated_text, "meta")
        ref.hide()
        ref.paragraph_clicked.connect(self.source_selected.emit)
        ref.action_requested.connect(self.action_requested.emit)
        return ref

    def _pick_title(self) -> str:
        for block in self.page.blocks:
            if block.block_type == "heading" and block.translated_text.strip() and block.block_index == 0:
                return block.translated_text.strip()
        for block in self.page.blocks:
            if block.block_type == "heading" and block.translated_text.strip():
                return block.translated_text.strip()
        return ""

    def _collect_meta_blocks(self) -> list[TranslationBlockView]:
        meta_blocks: list[TranslationBlockView] = []
        seen_title = False
        for block in self.page.blocks:
            text = (block.translated_text or "").strip()
            if not text or text == "（未翻译）":
                continue
            if block.block_type == "heading" and not seen_title:
                seen_title = True
                continue
            if block.block_type in {"header", "footer", "reference", "formula"}:
                continue
            if self._is_abstract_block(block) or self._is_keyword_block(block):
                break
            if block.extra.get("font_size", 0) >= 10.5 and len(text) <= 180 and self.page.page_number == 0:
                meta_blocks.append(block)
            elif meta_blocks:
                break
        return meta_blocks[:3]

    def _pick_original_title(self, translated_title: str) -> str:
        translated_title = (translated_title or "").strip()
        for block in self.page.blocks:
            source_text = (block.source_text or "").strip()
            translated_text = (block.translated_text or "").strip()
            if block.block_type != "heading":
                continue
            if not source_text:
                continue
            if translated_text == translated_title and source_text != translated_title:
                return source_text
        return ""

    def _group_blocks(self) -> dict[str, list[TranslationBlockView]]:
        groups: dict[str, list[TranslationBlockView]] = defaultdict(list)
        meta_indexes = {block.block_index for block in self._collect_meta_blocks()}
        title_text = self._pick_title()

        for block in self.page.blocks:
            text = (block.translated_text or "").strip()
            if not text or text == "（未翻译）":
                continue
            if block.block_index in meta_indexes:
                continue
            if block.block_type == "heading" and text == title_text:
                continue

            if block.block_type == "reference":
                groups["references"].append(block)
            elif block.block_type == "formula":
                groups["formula"].append(block)
            elif block.block_type == "figure_caption":
                groups["figure"].append(block)
            elif self._is_abstract_block(block):
                groups["abstract"].append(block)
            elif self._is_keyword_block(block):
                groups["keywords"].append(block)
            else:
                groups["body"].append(block)
        return groups

    def _is_abstract_block(self, block: TranslationBlockView) -> bool:
        source = (block.source_text or "").strip().lower()
        return source.startswith("abstract") or (block.source_text or "").startswith("摘要")

    def _is_keyword_block(self, block: TranslationBlockView) -> bool:
        source = (block.source_text or "").strip().lower()
        return source.startswith("keywords") or (block.source_text or "").startswith("关键词")

    def _render_section(
        self,
        layout: QVBoxLayout,
        title: str,
        blocks: list[TranslationBlockView],
        role: str,
        boxed: bool,
    ) -> None:
        if not blocks:
            return

        container = layout
        if boxed:
            section_card = QFrame()
            section_card.setObjectName("translatedSectionCard")
            section_layout = QVBoxLayout(section_card)
            section_layout.setContentsMargins(16, 14, 16, 14)
            section_layout.setSpacing(8)
            container = section_layout
            layout.addWidget(section_card)

        section_title = QLabel(title)
        section_title.setObjectName("translatedSectionTitle")
        container.addWidget(section_title)

        for block in blocks:
            para = _ParagraphLabel(
                source_text=block.source_text,
                translated_text=block.translated_text,
                role=role,
            )
            para.paragraph_clicked.connect(self.source_selected.emit)
            para.action_requested.connect(self.action_requested.emit)
            container.addWidget(para)
            self._paragraph_widgets[block.block_index] = para

    def _render_body(self, layout: QVBoxLayout, blocks: list[TranslationBlockView]) -> None:
        if not blocks:
            return

        for block in blocks:
            if block.block_type == "heading":
                label = QLabel(html.escape(block.translated_text))
                label.setObjectName("translatedHeadingBlock")
                label.setWordWrap(True)
                layout.addWidget(label)
                self._paragraph_widgets[block.block_index] = label
                continue

            para = _ParagraphLabel(
                source_text=block.source_text,
                translated_text=block.translated_text,
                role="body",
            )
            para.paragraph_clicked.connect(self.source_selected.emit)
            para.action_requested.connect(self.action_requested.emit)
            layout.addWidget(para)
            self._paragraph_widgets[block.block_index] = para

    def update_block_text(self, block_index: int, translated_text: str, source_text: str) -> None:
        paragraph = self._paragraph_widgets.get(block_index)
        if paragraph:
            if isinstance(paragraph, _ParagraphLabel):
                paragraph.set_translated_text(translated_text)
                paragraph.source_text = source_text
            else:
                paragraph.setText(html.escape(translated_text))

    def set_page_status(
        self,
        status: str,
        status_text: str,
        translated_blocks: int | None = None,
        total_blocks: int | None = None,
        failed_blocks: int | None = None,
    ) -> None:
        self.page.status = status
        self.page.status_text = status_text
        if translated_blocks is not None:
            self.page.translated_blocks = translated_blocks
        if total_blocks is not None:
            self.page.total_blocks = total_blocks
        if failed_blocks is not None:
            self.page.failed_blocks = failed_blocks
        self._apply_page_status()

    def get_anchor_widget_for_ratio(self, ratio: float):
        ratio = max(0.0, min(1.0, ratio))
        candidates: list[tuple[float, QWidget]] = []
        bbox_fallback: list[QWidget] = []

        page_height = 0.0
        for block in self.page.blocks:
            bbox = block.extra.get("bbox") or ()
            if len(bbox) >= 4:
                try:
                    page_height = max(page_height, float(bbox[3]))
                except Exception:  # noqa: BLE001
                    pass

        for block in self.page.blocks:
            widget = self._paragraph_widgets.get(block.block_index)
            if widget is None or widget.isHidden():
                continue
            bbox = block.extra.get("bbox") or ()
            if len(bbox) >= 4 and page_height > 0:
                try:
                    center = (float(bbox[1]) + float(bbox[3])) / 2
                    candidates.append((center / page_height, widget))
                    continue
                except Exception:  # noqa: BLE001
                    pass
            bbox_fallback.append(widget)

        if candidates:
            best_ratio, best_widget = min(candidates, key=lambda item: abs(item[0] - ratio))
            _ = best_ratio
            return best_widget

        if bbox_fallback:
            index = min(len(bbox_fallback) - 1, int(round(ratio * max(0, len(bbox_fallback) - 1))))
            return bbox_fallback[index]
        return None

    def _apply_page_status(self) -> None:
        if not self._status_banner or not self._status_title or not self._status_body:
            return

        self._status_banner.setProperty("status", self.page.status)
        self._status_banner.style().unpolish(self._status_banner)
        self._status_banner.style().polish(self._status_banner)

        title_map = {
            "untranslated": "尚未翻译",
            "translating": "正在翻译",
            "partial": "部分完成",
            "done": "译文已就绪",
            "failed": "翻译失败",
            "empty": "无可读内容",
        }
        self._status_title.setText(title_map.get(self.page.status, "当前状态"))
        self._status_body.setText(self.page.status_text or "")
        self._status_banner.setVisible(self.page.status != "done")
