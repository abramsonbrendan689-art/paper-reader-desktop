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

        for block in blocks:
            result = result_map.get(block.block_index)
            translated_text = result.translated_text if result else "（未翻译）"

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

        return TranslationPageView(
            page_number=page_number,
            blocks=views,
            heading=f"译文第 {page_number + 1} 页",
            meta=f"共 {len(views)} 个文本块",
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
