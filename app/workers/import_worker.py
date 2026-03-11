from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from app.services.library_service import LibraryService


class ImportWorker(QThread):
    progress = Signal(str)
    result_ready = Signal(list, list)
    error = Signal(str)

    def __init__(self, library_service: LibraryService, paths: list[str], parent=None):
        super().__init__(parent)
        self.library_service = library_service
        self.paths = paths

    def run(self) -> None:
        created = []
        errors: list[str] = []
        try:
            for raw in self.paths:
                if self.isInterruptionRequested():
                    break
                path = Path(raw)
                if path.is_dir():
                    self.progress.emit(f"导入文件夹: {path}")
                    imported, errs = self.library_service.import_folder(path)
                    created.extend(imported)
                    errors.extend(errs)
                    continue

                self.progress.emit(f"导入文件: {path.name}")
                try:
                    created.append(self.library_service.import_pdf(path))
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{path.name}: {exc}")

            self.result_ready.emit(created, errors)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
