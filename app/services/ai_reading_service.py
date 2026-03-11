from __future__ import annotations

from app.services.pdf_service import PDFService
from app.services.translation_service import TranslationService
from app.utils.text_utils import normalize_whitespace


class AIReadingService:
    def __init__(self, translation_service: TranslationService, pdf_service: PDFService):
        self.translation_service = translation_service
        self.pdf_service = pdf_service

    def summarize_text(self, text: str, provider_name: str | None = None) -> str:
        cleaned = normalize_whitespace(text)
        if not cleaned:
            return "未找到可用于摘要的文本。"

        provider = self.translation_service.resolve_provider(provider_name)
        summary = provider.summarize(text=cleaned, options={"reasoning": False})
        return f"【AI 生成内容】\n{summary}"

    def summarize_page(self, page_blocks: list[str], provider_name: str | None = None) -> str:
        content = "\n\n".join(x.strip() for x in page_blocks if x.strip())
        if not content:
            return "当前页暂无可总结文本。"
        return self.summarize_text(content, provider_name=provider_name)

    def summarize_paper_file(
        self,
        pdf_path: str,
        provider_name: str | None = None,
        max_pages: int = 12,
    ) -> str:
        full_text = self.pdf_service.extract_document_text(pdf_path, max_pages=max_pages)
        return self.summarize_text(full_text, provider_name=provider_name)

    def explain_paragraph(
        self,
        text: str,
        question: str = "请解释这段内容，并说明它在全文中的作用。",
        provider_name: str | None = None,
    ) -> str:
        provider = self.translation_service.resolve_provider(provider_name)
        answer = provider.explain(
            text=text,
            question=question,
            options={"reasoning": False},
        )
        return f"【AI 生成内容】\n{answer}"

    def _analyze_full_paper(
        self,
        pdf_path: str,
        provider_name: str | None = None,
        analysis_mode: bool | None = None,
        max_pages: int = 14,
    ) -> dict:
        use_reasoning = (
            self.translation_service.use_reasoning_for_analysis
            if analysis_mode is None
            else bool(analysis_mode)
        )
        provider = self.translation_service.resolve_provider(provider_name)
        full_text = self.pdf_service.extract_document_text(pdf_path, max_pages=max_pages)
        return provider.analyze_paper(
            full_text,
            options={"analysis_mode": use_reasoning},
        )

    def extract_innovations(
        self,
        pdf_path: str,
        provider_name: str | None = None,
        analysis_mode: bool | None = None,
    ) -> str:
        analysis = self._analyze_full_paper(pdf_path, provider_name, analysis_mode)
        innovation = analysis.get("innovation_points", "")
        if isinstance(innovation, list):
            innovation = "\n".join(f"- {x}" for x in innovation)
        return f"【AI 生成内容】\n{innovation or '未提取到创新点。'}"

    def extract_limitations(
        self,
        pdf_path: str,
        provider_name: str | None = None,
        analysis_mode: bool | None = None,
    ) -> str:
        analysis = self._analyze_full_paper(pdf_path, provider_name, analysis_mode)
        limitations = analysis.get("limitations", "")
        if isinstance(limitations, list):
            limitations = "\n".join(f"- {x}" for x in limitations)
        return f"【AI 生成内容】\n{limitations or '未提取到局限性。'}"

    def summarize_method(
        self,
        pdf_path: str,
        provider_name: str | None = None,
        analysis_mode: bool | None = None,
    ) -> str:
        analysis = self._analyze_full_paper(pdf_path, provider_name, analysis_mode)
        method = analysis.get("method", "")
        if isinstance(method, list):
            method = "\n".join(f"- {x}" for x in method)
        return f"【AI 生成内容】\n{method or '未提取到方法总结。'}"

    def summarize_conclusion(
        self,
        pdf_path: str,
        provider_name: str | None = None,
        analysis_mode: bool | None = None,
    ) -> str:
        analysis = self._analyze_full_paper(pdf_path, provider_name, analysis_mode)
        results = analysis.get("results", "")
        if isinstance(results, list):
            results = "\n".join(f"- {x}" for x in results)
        return f"【AI 生成内容】\n{results or '未提取到结论总结。'}"

    def generate_reading_notes(
        self,
        pdf_path: str,
        provider_name: str | None = None,
        analysis_mode: bool | None = None,
    ) -> str:
        analysis = self._analyze_full_paper(pdf_path, provider_name, analysis_mode)
        background = analysis.get("background", "")
        problem = analysis.get("problem", "")
        method = analysis.get("method", "")
        contributions = analysis.get("contributions", "")
        results = analysis.get("results", "")
        limitations = analysis.get("limitations", "")

        note = (
            "【AI 生成阅读笔记】\n"
            f"研究背景：{background}\n\n"
            f"研究问题：{problem}\n\n"
            f"方法：{method}\n\n"
            f"贡献：{contributions}\n\n"
            f"结论：{results}\n\n"
            f"局限性：{limitations}"
        )
        return note
