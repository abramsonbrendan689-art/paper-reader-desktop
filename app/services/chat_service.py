from __future__ import annotations

from app.models.chat_message import ChatMessage
from app.repositories.chat_repository import ChatRepository
from app.repositories.translation_repository import TranslationRepository
from app.services.ai_reading_service import AIReadingService
from app.services.pdf_service import PDFService
from app.services.translation_service import TranslationService


class ChatService:
    def __init__(
        self,
        chat_repo: ChatRepository,
        translation_repo: TranslationRepository,
        translation_service: TranslationService,
        ai_reading_service: AIReadingService,
        pdf_service: PDFService,
    ):
        self.chat_repo = chat_repo
        self.translation_repo = translation_repo
        self.translation_service = translation_service
        self.ai_reading_service = ai_reading_service
        self.pdf_service = pdf_service

    def list_messages(self, paper_id: int) -> list[dict[str, str]]:
        rows = self.chat_repo.list_by_paper(paper_id)
        return [{"role": x.role, "content": x.content} for x in rows]

    def save_message(self, paper_id: int, role: str, content: str) -> None:
        self.chat_repo.create(ChatMessage(paper_id=paper_id, role=role, content=content))

    def clear_messages(self, paper_id: int) -> None:
        self.chat_repo.clear_by_paper(paper_id)

    def build_context(
        self,
        paper_id: int,
        pdf_path: str,
        current_page: int,
        selected_text: str,
        mode: str,
        translated_text: str = "",
    ) -> str:
        mode = (mode or "custom").strip().lower()

        if mode == "selected_text":
            return selected_text.strip()

        if mode == "current_page":
            blocks = self.pdf_service.extract_page_blocks(pdf_path, current_page)
            return "\n".join(b.text for b in blocks if b.text.strip())[:12000]

        if mode == "paper_summary":
            return self.ai_reading_service.summarize_paper_file(pdf_path=pdf_path, max_pages=10)

        if mode == "translated_content":
            if translated_text.strip():
                return translated_text.strip()
            cached = self.translation_repo.get_page_blocks(
                paper_id=paper_id,
                page_number=current_page,
                provider_name=self.translation_service.get_default_provider_name(),
            )
            return "\n".join(x.translated_text for x in cached if (x.translated_text or "").strip())[:12000]

        return ""

    def ask(
        self,
        user_message: str,
        history: list[dict[str, str]],
        context_text: str,
        analysis_mode: bool = False,
    ) -> str:
        provider = self.translation_service.resolve_provider()
        if hasattr(provider, "build_chat_messages"):
            messages = provider.build_chat_messages(history, user_message, context_text=context_text)
        else:
            messages = history + [{"role": "user", "content": user_message.strip()}]
        return provider.chat(messages=messages, options={"analysis_mode": analysis_mode})
