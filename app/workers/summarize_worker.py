from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from app.services.ai_reading_service import AIReadingService


class SummarizeWorker(QThread):
    result_ready = Signal(str)
    error = Signal(str)

    def __init__(
        self,
        ai_reading_service: AIReadingService,
        mode: str,
        payload: dict,
        provider_name: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.ai_reading_service = ai_reading_service
        self.mode = mode
        self.payload = payload
        self.provider_name = provider_name

    def run(self) -> None:
        try:
            if self.mode == "paper":
                result = self.ai_reading_service.summarize_paper_file(
                    pdf_path=self.payload["pdf_path"],
                    provider_name=self.provider_name,
                )
            elif self.mode == "page":
                result = self.ai_reading_service.summarize_page(
                    page_blocks=self.payload["blocks"],
                    provider_name=self.provider_name,
                )
            elif self.mode == "explain":
                result = self.ai_reading_service.explain_paragraph(
                    text=self.payload.get("text", ""),
                    question=self.payload.get("question", ""),
                    provider_name=self.provider_name,
                )
            elif self.mode == "innovation":
                result = self.ai_reading_service.extract_innovations(
                    pdf_path=self.payload["pdf_path"],
                    provider_name=self.provider_name,
                    analysis_mode=self.payload.get("analysis_mode"),
                )
            elif self.mode == "limitation":
                result = self.ai_reading_service.extract_limitations(
                    pdf_path=self.payload["pdf_path"],
                    provider_name=self.provider_name,
                    analysis_mode=self.payload.get("analysis_mode"),
                )
            elif self.mode == "method":
                result = self.ai_reading_service.summarize_method(
                    pdf_path=self.payload["pdf_path"],
                    provider_name=self.provider_name,
                    analysis_mode=self.payload.get("analysis_mode"),
                )
            elif self.mode == "conclusion":
                result = self.ai_reading_service.summarize_conclusion(
                    pdf_path=self.payload["pdf_path"],
                    provider_name=self.provider_name,
                    analysis_mode=self.payload.get("analysis_mode"),
                )
            elif self.mode == "reading_note":
                result = self.ai_reading_service.generate_reading_notes(
                    pdf_path=self.payload["pdf_path"],
                    provider_name=self.provider_name,
                    analysis_mode=self.payload.get("analysis_mode"),
                )
            else:
                result = "不支持的任务类型"
            self.result_ready.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
