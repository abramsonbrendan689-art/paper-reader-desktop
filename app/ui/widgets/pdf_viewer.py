from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.services.pdf_service import PDFService


class PDFViewerWidget(QWidget):
    page_changed = Signal(int)

    def __init__(self, pdf_service: PDFService, parent=None):
        super().__init__(parent)
        self.pdf_service = pdf_service
        self.pdf_path: str | None = None
        self.page_count = 0
        self.current_page = 0
        self.zoom = 1.4

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.prev_btn = QPushButton("上一页")
        self.next_btn = QPushButton("下一页")
        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.setMaximum(1)
        self.page_info = QLabel(" / 0")
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(80, 250)
        self.zoom_slider.setValue(140)
        self.zoom_label = QLabel("缩放 140%")

        toolbar.addWidget(self.prev_btn)
        toolbar.addWidget(self.next_btn)
        toolbar.addWidget(QLabel("页码"))
        toolbar.addWidget(self.page_spin)
        toolbar.addWidget(self.page_info)
        toolbar.addSpacing(20)
        toolbar.addWidget(self.zoom_label)
        toolbar.addWidget(self.zoom_slider)
        root.addLayout(toolbar)

        self.image_label = QLabel("请先导入并打开 PDF")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: #f4f5f7; border: 1px solid #d0d7de;")
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll.setWidget(self.image_label)
        root.addWidget(self.scroll)

        self.prev_btn.clicked.connect(self.prev_page)
        self.next_btn.clicked.connect(self.next_page)
        self.page_spin.valueChanged.connect(self._on_page_spin_changed)
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)

    def load_pdf(self, pdf_path: str) -> None:
        self.pdf_path = str(Path(pdf_path))
        self.page_count = self.pdf_service.page_count(self.pdf_path)
        self.current_page = 0
        self.page_spin.blockSignals(True)
        self.page_spin.setMaximum(max(1, self.page_count))
        self.page_spin.setValue(1)
        self.page_spin.blockSignals(False)
        self.page_info.setText(f" / {self.page_count}")
        self.render_current_page()

    def render_current_page(self) -> None:
        if not self.pdf_path:
            return
        pix = self.pdf_service.render_page(self.pdf_path, self.current_page, zoom=self.zoom)
        image_format = QImage.Format.Format_RGB888
        image = QImage(pix.samples, pix.width, pix.height, pix.stride, image_format).copy()
        qpix = QPixmap.fromImage(image)
        self.image_label.setPixmap(qpix)
        self.image_label.adjustSize()
        self.page_changed.emit(self.current_page)

    def _on_page_spin_changed(self, value: int) -> None:
        if self.page_count <= 0:
            return
        self.current_page = max(0, min(value - 1, self.page_count - 1))
        self.render_current_page()

    def _on_zoom_changed(self, value: int) -> None:
        self.zoom = value / 100.0
        self.zoom_label.setText(f"缩放 {value}%")
        self.render_current_page()

    def prev_page(self) -> None:
        if self.current_page <= 0:
            return
        self.current_page -= 1
        self.page_spin.blockSignals(True)
        self.page_spin.setValue(self.current_page + 1)
        self.page_spin.blockSignals(False)
        self.render_current_page()

    def next_page(self) -> None:
        if self.current_page >= self.page_count - 1:
            return
        self.current_page += 1
        self.page_spin.blockSignals(True)
        self.page_spin.setValue(self.current_page + 1)
        self.page_spin.blockSignals(False)
        self.render_current_page()
