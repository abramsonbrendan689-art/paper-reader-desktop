from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QLabel, QWidget


class Snackbar(QWidget):
    def __init__(self, parent: QWidget, text: str, duration_ms: int = 2600):
        super().__init__(parent)
        self.setObjectName("Snackbar")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.SubWindow)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.label = QLabel(text, self)
        self.label.setObjectName("SnackbarText")
        self.label.adjustSize()
        self.resize(self.label.width() + 12, self.label.height() + 8)
        self._position_center_bottom()

        QTimer.singleShot(duration_ms, self.close)

    def _position_center_bottom(self) -> None:
        if not self.parent():
            return
        parent = self.parentWidget()
        if not parent:
            return
        x = max(12, (parent.width() - self.width()) // 2)
        y = max(12, parent.height() - self.height() - 24)
        self.move(x, y)

    @staticmethod
    def show_message(parent: QWidget, text: str, duration_ms: int = 2600) -> None:
        bar = Snackbar(parent, text, duration_ms)
        bar.show()

