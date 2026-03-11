from __future__ import annotations

import html
from collections import defaultdict

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QContextMenuEvent, QGuiApplication
from PySide6.QtWidgets import QFrame, QLabel, QMenu, QVBoxLayout

from app.models.translation_page import TranslationBlockView, TranslationPageView
from app.ui.theme import apply_elevation


class _ParagraphLabel(QLabel):
    paragraph_clicked = Signal(str)

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
        copy_translated.triggered.connect(
            lambda: QGuiApplication.clipboard().setText(self.translated_text)
        )
        copy_source.triggered.connect(lambda: QGuiApplication.clipboard().setText(self.source_text))
        menu.addAction(copy_translated)
        menu.addAction(copy_source)
        menu.exec(event.globalPos())


class TranslatedPageWidget(QFrame):
    source_selected = Signal(str)

    def __init__(self, page: TranslationPageView, parent=None):
        super().__init__(parent)
        self.page = page
        self._paragraph_widgets: dict[int, QLabel] = {}
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
