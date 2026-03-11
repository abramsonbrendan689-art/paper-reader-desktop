from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.core.container import AppContainer
from app.core.logging import logger
from app.ui.main_window import MainWindow
from app.ui.theme import apply_app_theme, material3_light_tokens


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Literature Reader")
    apply_app_theme(app, material3_light_tokens())

    try:
        container = AppContainer.build()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Application initialization failed: {}", exc)
        raise

    window = MainWindow(container)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

