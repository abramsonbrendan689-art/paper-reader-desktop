from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap, QWheelEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.services.pdf_service import PDFService
from app.ui.theme import apply_elevation, material_icon


@dataclass(slots=True)
class _PageWidgetState:
    page_index: int
    page_size: tuple[float, float]
    card: QFrame
    image_label: QLabel
    rendered_zoom_key: int = -1


class PDFReaderWidget(QWidget):
    current_page_changed = Signal(int)
    visible_pages_changed = Signal(list)
    scroll_ratio_changed = Signal(float)
    page_count_changed = Signal(int)

    def __init__(self, pdf_service: PDFService, parent=None, show_toolbar: bool = True):
        super().__init__(parent)
        self.pdf_service = pdf_service
        self.show_toolbar = show_toolbar
        self.pdf_path: str | None = None

        self.page_count = 0
        self.current_page = 0
        self.zoom = 1.3
        self.zoom_mode = "fit_width"  # fit_width / fit_page / custom

        self._page_states: list[_PageWidgetState] = []
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.timeout.connect(self._render_visible_pages)
        self._pending_center_anchor: float | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        pane = QFrame()
        pane.setObjectName("PaneSurface")
        apply_elevation(pane, "card")

        pane_layout = QVBoxLayout(pane)
        pane_layout.setContentsMargins(12, 12, 12, 12)
        pane_layout.setSpacing(10)

        self.toolbar_container = QFrame()
        self.toolbar_container.setObjectName("ReaderToolSurface")
        toolbar = QHBoxLayout(self.toolbar_container)
        toolbar.setContentsMargins(8, 8, 8, 8)
        toolbar.setSpacing(8)

        self.prev_btn = QPushButton("上一页")
        self.prev_btn.setObjectName("ReaderToolButton")
        self.prev_btn.setIcon(material_icon("prev"))

        self.next_btn = QPushButton("下一页")
        self.next_btn.setObjectName("ReaderToolButton")
        self.next_btn.setIcon(material_icon("next"))

        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.setMaximum(1)
        self.page_info = QLabel(" / 0")
        self.page_info.setObjectName("SectionSupporting")

        self.zoom_combo = QComboBox()
        self.zoom_combo.addItems(
            [
                "适合宽度",
                "适合页面",
                "100%",
                "125%",
                "150%",
                "200%",
            ]
        )
        self.zoom_combo.setCurrentText("适合宽度")

        self.zoom_label = QLabel("缩放: 100%")
        self.zoom_label.setObjectName("SectionSupporting")

        toolbar.addWidget(self.prev_btn)
        toolbar.addWidget(self.next_btn)
        toolbar.addSpacing(8)
        toolbar.addWidget(QLabel("页码"))
        toolbar.addWidget(self.page_spin)
        toolbar.addWidget(self.page_info)
        toolbar.addStretch(1)
        toolbar.addWidget(self.zoom_combo)
        toolbar.addWidget(self.zoom_label)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(20, 24, 20, 28)
        self.content_layout.setSpacing(28)
        self.content_layout.addStretch(1)

        self.empty_state = QLabel("尚未打开文献。请从左侧文献库选择或导入 PDF。")
        self.empty_state.setObjectName("EmptyState")
        self.empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.scroll_area.setWidget(self.content_widget)

        pane_layout.addWidget(self.toolbar_container)
        pane_layout.addWidget(self.scroll_area, 1)
        pane_layout.addWidget(self.empty_state)
        root.addWidget(pane)

        self.toolbar_container.setVisible(self.show_toolbar)

        self.prev_btn.clicked.connect(self.prev_page)
        self.next_btn.clicked.connect(self.next_page)
        self.page_spin.valueChanged.connect(self._on_page_spin_changed)
        self.zoom_combo.currentTextChanged.connect(self.set_zoom_preset)

        self.scroll_area.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)
        self.scroll_area.viewport().installEventFilter(self)
        self._refresh_empty_state()

    def eventFilter(self, watched, event):
        if watched is self.scroll_area.viewport() and isinstance(event, QWheelEvent):
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                delta = event.angleDelta().y()
                if delta > 0:
                    self.zoom_in()
                elif delta < 0:
                    self.zoom_out()
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.page_count == 0:
            return
        if self.zoom_mode in {"fit_width", "fit_page"}:
            self._apply_zoom(self._compute_auto_zoom(self.zoom_mode), mode=self.zoom_mode)

    def load_pdf(self, pdf_path: str, initial_page: int = 0, initial_scroll_ratio: float = 0.0) -> None:
        self.pdf_path = str(Path(pdf_path))
        self.page_count = self.pdf_service.page_count(self.pdf_path)
        self.current_page = max(0, min(initial_page, max(0, self.page_count - 1)))

        self.page_spin.blockSignals(True)
        self.page_spin.setMaximum(max(1, self.page_count))
        self.page_spin.setValue(self.current_page + 1)
        self.page_spin.blockSignals(False)
        self.page_info.setText(f" / {self.page_count}")
        self.page_count_changed.emit(self.page_count)

        self._build_page_widgets()
        self._apply_zoom(self._compute_auto_zoom(self.zoom_mode), mode=self.zoom_mode)
        self._refresh_empty_state()
        QTimer.singleShot(0, lambda: self._restore_position(self.current_page, initial_scroll_ratio))

    def _build_page_widgets(self) -> None:
        while self.content_layout.count() > 1:
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self._page_states.clear()
        if not self.pdf_path:
            return

        sizes = self.pdf_service.get_page_sizes(self.pdf_path)
        for idx, size in enumerate(sizes):
            card = QFrame()
            card.setObjectName("pdfPageCard")
            apply_elevation(card, "card")

            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 14, 14, 14)
            card_layout.setSpacing(8)

            title = QLabel(f"第 {idx + 1} 页")
            title.setObjectName("pdfPageTitle")

            image_label = QLabel("页面加载中...")
            image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            image_label.setObjectName("pdfPageImage")

            card_layout.addWidget(title)
            card_layout.addWidget(image_label)

            self.content_layout.insertWidget(self.content_layout.count() - 1, card, 0, Qt.AlignmentFlag.AlignHCenter)
            self._page_states.append(
                _PageWidgetState(
                    page_index=idx,
                    page_size=size,
                    card=card,
                    image_label=image_label,
                )
            )

    def _restore_position(self, page_number: int, scroll_ratio: float) -> None:
        self.jump_to_page(page_number)
        if scroll_ratio > 0:
            bar = self.scroll_area.verticalScrollBar()
            bar.setValue(int(max(0.0, min(1.0, scroll_ratio)) * bar.maximum()))

    def _compute_auto_zoom(self, mode: str) -> float:
        if not self._page_states:
            return 1.0

        page_w, page_h = self._page_states[0].page_size
        viewport_w = max(400, self.scroll_area.viewport().width() - 24)
        viewport_h = max(300, self.scroll_area.viewport().height() - 64)

        if mode == "fit_page":
            return max(0.4, min(3.0, min(viewport_w / page_w, viewport_h / page_h)))
        return max(0.4, min(3.0, viewport_w / page_w))

    def set_zoom_preset(self, text: str) -> None:
        text = text.strip()
        if text == "适合宽度":
            self._apply_zoom(self._compute_auto_zoom("fit_width"), mode="fit_width")
            return
        if text == "适合页面":
            self._apply_zoom(self._compute_auto_zoom("fit_page"), mode="fit_page")
            return

        if text.endswith("%"):
            try:
                value = float(text.replace("%", "")) / 100.0
            except Exception:  # noqa: BLE001
                return
            self._apply_zoom(value, mode="custom")

    def zoom_in(self) -> None:
        self._set_custom_zoom(self.zoom * 1.12)

    def zoom_out(self) -> None:
        self._set_custom_zoom(self.zoom / 1.12)

    def _set_custom_zoom(self, zoom: float) -> None:
        self._apply_zoom(zoom, mode="custom")
        self.zoom_combo.blockSignals(True)
        self.zoom_combo.setCurrentText(f"{int(round(self.zoom * 100))}%")
        self.zoom_combo.blockSignals(False)

    def _apply_zoom(self, zoom: float, mode: str | None = None) -> None:
        if not self._page_states:
            return

        zoom = max(0.4, min(3.0, zoom))
        self._pending_center_anchor = self._capture_view_anchor()

        self.zoom = zoom
        if mode:
            self.zoom_mode = mode

        zoom_key = int(round(self.zoom * 100))
        self.zoom_label.setText(f"缩放: {zoom_key}%")

        for state in self._page_states:
            base_w, base_h = state.page_size
            draw_w = int(base_w * self.zoom)
            draw_h = int(base_h * self.zoom)
            state.image_label.setMinimumSize(draw_w, draw_h)
            state.image_label.setMaximumSize(draw_w, draw_h)

        QTimer.singleShot(0, self._restore_view_anchor)
        self._schedule_render()

    def _capture_view_anchor(self) -> float:
        bar = self.scroll_area.verticalScrollBar()
        viewport_h = self.scroll_area.viewport().height()
        denominator = bar.maximum() + viewport_h
        if denominator <= 0:
            return 0.0
        return (bar.value() + viewport_h / 2) / denominator

    def _restore_view_anchor(self) -> None:
        if self._pending_center_anchor is None:
            return
        bar = self.scroll_area.verticalScrollBar()
        viewport_h = self.scroll_area.viewport().height()
        denominator = bar.maximum() + viewport_h
        if denominator > 0:
            center = max(0.0, min(1.0, self._pending_center_anchor)) * denominator
            bar.setValue(int(center - viewport_h / 2))
        self._pending_center_anchor = None

    def _schedule_render(self) -> None:
        self._render_timer.start(50)

    def _render_visible_pages(self) -> None:
        if not self.pdf_path or not self._page_states:
            return

        visible = self.get_visible_page_numbers()
        if not visible:
            return

        to_render: set[int] = set(visible)
        for p in visible:
            to_render.add(max(0, p - 1))
            to_render.add(max(0, p - 2))
            to_render.add(min(self.page_count - 1, p + 1))
            to_render.add(min(self.page_count - 1, p + 2))

        zoom_key = int(round(self.zoom * 100))

        for page_index in sorted(to_render):
            state = self._page_states[page_index]
            if state.rendered_zoom_key == zoom_key:
                continue

            try:
                pix = self.pdf_service.render_page(self.pdf_path, page_index, zoom=self.zoom)
                image = QImage(
                    pix.samples,
                    pix.width,
                    pix.height,
                    pix.stride,
                    QImage.Format.Format_RGB888,
                ).copy()
                qpix = QPixmap.fromImage(image)
                state.image_label.setPixmap(qpix)
                state.rendered_zoom_key = zoom_key
            except Exception:  # noqa: BLE001
                state.image_label.setText(f"第 {page_index + 1} 页渲染失败")

    def _on_scroll_changed(self, value: int) -> None:
        _ = value
        self._update_current_page_by_scroll()
        self._schedule_render()

        bar = self.scroll_area.verticalScrollBar()
        ratio = bar.value() / bar.maximum() if bar.maximum() > 0 else 0.0
        self.scroll_ratio_changed.emit(ratio)

    def _update_current_page_by_scroll(self) -> None:
        if not self._page_states:
            return

        bar = self.scroll_area.verticalScrollBar()
        viewport_h = self.scroll_area.viewport().height()
        center_y = bar.value() + viewport_h / 2

        best_page = self.current_page
        best_dist = float("inf")

        for state in self._page_states:
            y = state.card.y()
            h = state.card.height()
            page_center = y + h / 2
            dist = abs(page_center - center_y)
            if dist < best_dist:
                best_dist = dist
                best_page = state.page_index

        if best_page != self.current_page:
            self.current_page = best_page
            self.page_spin.blockSignals(True)
            self.page_spin.setValue(self.current_page + 1)
            self.page_spin.blockSignals(False)
            self.current_page_changed.emit(self.current_page)

        self.visible_pages_changed.emit(self.get_visible_page_numbers())

    def get_visible_page_numbers(self) -> list[int]:
        if not self._page_states:
            return []

        bar = self.scroll_area.verticalScrollBar()
        top = bar.value()
        bottom = top + self.scroll_area.viewport().height()

        visible: list[int] = []
        for state in self._page_states:
            y = state.card.y()
            h = state.card.height()
            if y + h >= top and y <= bottom:
                visible.append(state.page_index)
        return visible

    def get_current_page(self) -> int:
        return self.current_page

    def get_page_count(self) -> int:
        return self.page_count

    def get_scroll_ratio(self) -> float:
        bar = self.scroll_area.verticalScrollBar()
        return bar.value() / bar.maximum() if bar.maximum() > 0 else 0.0

    def jump_to_page(self, page_number: int) -> None:
        if not self._page_states:
            return

        page_number = max(0, min(page_number, self.page_count - 1))
        state = self._page_states[page_number]
        bar = self.scroll_area.verticalScrollBar()
        bar.setValue(max(0, state.card.y() - 20))
        self.current_page = page_number
        self.page_spin.blockSignals(True)
        self.page_spin.setValue(page_number + 1)
        self.page_spin.blockSignals(False)
        self.current_page_changed.emit(page_number)
        self._schedule_render()

    def prev_page(self) -> None:
        self.jump_to_page(self.current_page - 1)

    def next_page(self) -> None:
        self.jump_to_page(self.current_page + 1)

    def _on_page_spin_changed(self, value: int) -> None:
        if self.page_count <= 0:
            return
        self.jump_to_page(value - 1)

    def _refresh_empty_state(self) -> None:
        has_pdf = bool(self.pdf_path and self.page_count > 0)
        self.scroll_area.setVisible(has_pdf)
        self.empty_state.setVisible(not has_pdf)

    def get_current_page_text_hint(self) -> str:
        return f"第 {self.current_page + 1} 页"
