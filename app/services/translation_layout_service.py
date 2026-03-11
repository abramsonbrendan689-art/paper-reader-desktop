from __future__ import annotations

from app.models.paper import PaperBlock
from app.models.translation_page import TranslationBlockView, TranslationPageView
from app.services.translation_service import TranslationResult


class TranslationLayoutService:
    """
    Rebuild block-level translation data into page-level reading views.
    Storage stays block-based; only the presentation layer becomes page-oriented.
    """

    def build_page_view(
        self,
        page_number: int,
        blocks: list[PaperBlock],
        results: list[TranslationResult] | None = None,
    ) -> TranslationPageView:
        result_map = {item.block_index: item for item in (results or [])}
        views: list[TranslationBlockView] = []
        total_blocks = 0
        translated_blocks = 0
        failed_blocks = 0

        for block in blocks:
            result = result_map.get(block.block_index)
            translated_text = result.translated_text if result else ""

            if block.block_type not in {"header", "footer"} and block.text.strip():
                total_blocks += 1
                if translated_text.strip():
                    if translated_text.startswith("翻译失败"):
                        failed_blocks += 1
                    else:
                        translated_blocks += 1

            views.append(
                TranslationBlockView(
                    page_number=page_number,
                    block_index=block.block_index,
                    block_type=block.block_type,
                    source_text=block.text,
                    translated_text=translated_text,
                    title=self._title_for_block(block),
                    extra={
                        "font_size": block.avg_font_size,
                        "span_count": block.span_count,
                        "bbox": block.bbox,
                    },
                )
            )

        status, status_text = self._build_status(
            total_blocks=total_blocks,
            translated_blocks=translated_blocks,
            failed_blocks=failed_blocks,
            has_results=results is not None,
        )

        return TranslationPageView(
            page_number=page_number,
            blocks=views,
            heading=f"译文第 {page_number + 1} 页",
            meta=f"共 {len(views)} 个文本块",
            status=status,
            status_text=status_text,
            translated_blocks=translated_blocks,
            total_blocks=total_blocks,
            failed_blocks=failed_blocks,
        )

    @staticmethod
    def _title_for_block(block: PaperBlock) -> str:
        block_type = block.block_type
        if block_type == "heading":
            return "标题"
        if block_type == "figure_caption":
            return "图表说明"
        if block_type == "formula":
            return "公式相关"
        if block_type == "reference":
            return "参考文献"
        if block_type in {"header", "footer"}:
            return "页眉页脚"
        return "正文"

    @staticmethod
    def _build_status(
        total_blocks: int,
        translated_blocks: int,
        failed_blocks: int,
        has_results: bool,
    ) -> tuple[str, str]:
        if total_blocks <= 0:
            return "empty", "当前页未识别到可阅读文本块。"
        if not has_results:
            return "untranslated", f"当前页尚未翻译，可点击顶部按钮开始翻译。共 {total_blocks} 个块。"
        if translated_blocks == 0 and failed_blocks > 0:
            return "failed", f"当前页翻译失败，共 {failed_blocks} 个块失败。"
        if translated_blocks <= 0:
            return "untranslated", f"当前页尚未生成译文，共 {total_blocks} 个块。"
        if translated_blocks < total_blocks:
            return "partial", f"当前页已完成 {translated_blocks}/{total_blocks} 个块。"
        return "done", f"当前页译文已完成，共 {translated_blocks} 个块。"
