from __future__ import annotations

from app.services.pdf_service import PDFService
from app.ui.widgets.pdf_reader_widget import PDFReaderWidget


class SourcePdfReader(PDFReaderWidget):
    """
    Semantic alias for the original PDF reader widget.
    Kept as a standalone component to make parallel-reader composition clearer.
    """

    def __init__(self, pdf_service: PDFService, parent=None):
        super().__init__(pdf_service=pdf_service, parent=parent, show_toolbar=False)
