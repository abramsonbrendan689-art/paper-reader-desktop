from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from app.services.chat_service import ChatService


class ChatWorker(QThread):
    result_ready = Signal(str)
    error = Signal(str)

    def __init__(
        self,
        chat_service: ChatService,
        user_message: str,
        history: list[dict[str, str]],
        context_text: str,
        analysis_mode: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.chat_service = chat_service
        self.user_message = user_message
        self.history = history
        self.context_text = context_text
        self.analysis_mode = analysis_mode

    def run(self) -> None:
        try:
            reply = self.chat_service.ask(
                user_message=self.user_message,
                history=self.history,
                context_text=self.context_text,
                analysis_mode=self.analysis_mode,
            )
            self.result_ready.emit(reply)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
