from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QGraphicsDropShadowEffect, QWidget

from app.ui.theme.design_tokens import DesignTokens


def apply_app_theme(app: QApplication, tokens: DesignTokens) -> None:
    app.setStyleSheet(build_stylesheet(tokens))


def build_stylesheet(tokens: DesignTokens) -> str:
    c = tokens.colors
    s = tokens.shape
    t = tokens.typography
    sp = tokens.spacing

    return f"""
    * {{
        font-family: "Microsoft YaHei UI", "Segoe UI", "PingFang SC", sans-serif;
        color: {c.text_primary};
        font-size: {t.body}px;
    }}

    QWidget#AppRoot {{
        background: {c.background};
    }}

    QWidget#TopAppBar {{
        background: {c.surface};
        border: 1px solid {c.outline_variant};
        border-radius: {s.lg}px;
    }}

    QStatusBar {{
        background: {c.surface};
        border-top: 1px solid {c.outline_variant};
        color: {c.text_secondary};
    }}

    QFrame#PaneSurface {{
        background: {c.surface};
        border: 1px solid {c.outline_variant};
        border-radius: {s.lg}px;
    }}

    QFrame#ReaderMainSurface {{
        background: {c.surface_container};
        border: 1px solid {c.outline_variant};
        border-radius: {s.xl}px;
    }}

    QFrame#ReaderColumnShell {{
        background: {c.sidebar_surface};
        border: 1px solid {c.outline_variant};
        border-radius: {s.lg}px;
    }}

    QFrame#ReaderToolSurface {{
        background: {c.surface};
        border: 1px solid {c.outline_variant};
        border-radius: {s.lg}px;
    }}

    QFrame#ReaderColumnHeader {{
        background: transparent;
        border: none;
        border-bottom: 1px solid {c.outline_variant};
    }}

    QLabel#ReaderColumnTitle {{
        color: {c.text_primary};
        font-size: {t.subtitle}px;
        font-weight: 700;
    }}

    QLabel#ReaderColumnSubtitle {{
        color: {c.text_secondary};
        font-size: {t.supporting}px;
    }}

    QLabel#AppTitle {{
        color: {c.text_primary};
        font-size: {t.subtitle}px;
        font-weight: 700;
    }}

    QLabel#AppSubtitle,
    QLabel#SectionSupporting,
    QLabel#ReaderMetaLabel {{
        color: {c.text_secondary};
        font-size: {t.supporting}px;
    }}

    QLabel#SectionTitle {{
        color: {c.text_primary};
        font-size: {t.subtitle}px;
        font-weight: 700;
    }}

    QLineEdit#TopSearchInput,
    QLineEdit#LibrarySearchInput {{
        background: {c.surface_variant};
        border: 1px solid {c.outline_variant};
        border-radius: {s.lg}px;
        padding: {sp.s8}px {sp.s12}px;
    }}

    QLineEdit#TopSearchInput:focus,
    QLineEdit#LibrarySearchInput:focus,
    QTextEdit:focus,
    QPlainTextEdit:focus,
    QComboBox:focus,
    QSpinBox:focus {{
        border: 2px solid {c.primary};
        background: {c.surface};
    }}

    QLineEdit,
    QTextEdit,
    QPlainTextEdit,
    QComboBox,
    QSpinBox {{
        background: {c.surface};
        border: 1px solid {c.outline_variant};
        border-radius: {s.md}px;
        padding: {sp.s8}px {sp.s12}px;
        selection-background-color: {c.selected};
    }}

    QPushButton#AppBarButton,
    QToolButton#AppBarButton {{
        background: {c.surface_variant};
        border: 1px solid {c.outline_variant};
        border-radius: {s.md}px;
        padding: {sp.s8}px {sp.s12}px;
        text-align: left;
    }}

    QPushButton#AppBarButton:hover,
    QToolButton#AppBarButton:hover,
    QPushButton#ReaderToolButton:hover,
    QPushButton#ChipButton:hover {{
        background: {c.hover};
    }}

    QPushButton#AppBarButton:pressed,
    QToolButton#AppBarButton:pressed,
    QPushButton#ReaderToolButton:pressed,
    QPushButton#ChipButton:pressed {{
        background: {c.pressed};
    }}

    QPushButton#AppBarButton:disabled,
    QToolButton#AppBarButton:disabled {{
        background: {c.surface_container_high};
        border-color: {c.outline_variant};
        color: {c.disabled};
    }}

    QToolButton#AppBarButton::menu-indicator {{
        width: 0px;
    }}

    QPushButton#ReaderToolButton {{
        background: {c.surface};
        border: 1px solid {c.outline_variant};
        border-radius: {s.lg}px;
        padding: {sp.s8}px {sp.s12}px;
    }}

    QPushButton#ChipButton {{
        background: {c.surface};
        border: 1px solid {c.outline_variant};
        border-radius: {s.md}px;
        padding: {sp.s4}px {sp.s8}px;
        color: {c.text_secondary};
        font-size: {t.supporting}px;
    }}

    QPushButton#SegmentButton {{
        background: {c.surface};
        border: 1px solid {c.outline_variant};
        border-radius: {s.md}px;
        padding: {sp.s8}px {sp.s8}px;
        color: {c.text_secondary};
    }}

    QPushButton#SegmentButton:checked {{
        background: {c.primary_container};
        border-color: {c.primary};
        color: {c.on_primary_container};
        font-weight: 700;
    }}

    QCheckBox {{
        spacing: {sp.s8}px;
        color: {c.text_secondary};
    }}

    QMenu {{
        background: {c.surface};
        border: 1px solid {c.outline_variant};
        border-radius: {s.md}px;
        padding: {sp.s4}px;
    }}

    QMenu::item {{
        padding: {sp.s8}px {sp.s12}px;
        border-radius: {s.sm}px;
    }}

    QMenu::item:selected {{
        background: {c.hover};
    }}

    QListWidget,
    QTableWidget,
    QScrollArea {{
        background: transparent;
        border: none;
    }}

    QListWidget#PaperList::item {{
        margin: {sp.s4}px 0;
        padding: 0;
        border-radius: {s.md}px;
    }}

    QListWidget#PaperList::item:selected {{
        background: transparent;
    }}

    QWidget#PaperListCard {{
        background: {c.surface};
        border: 1px solid {c.outline_variant};
        border-radius: {s.lg}px;
    }}

    QWidget#PaperListCard[active="true"] {{
        background: {c.primary_container};
        border: 1px solid {c.primary};
    }}

    QLabel#PaperCardTitle {{
        color: {c.text_primary};
        font-size: {t.body}px;
        font-weight: 700;
    }}

    QLabel#PaperCardMeta {{
        color: {c.text_secondary};
        font-size: {t.supporting}px;
    }}

    QLabel#PaperCardChip {{
        color: {c.on_primary_container};
        background: {c.primary_container};
        border-radius: {s.sm}px;
        padding: {sp.s4}px {sp.s8}px;
        font-size: {t.label}px;
    }}

    QFrame#pdfPageCard {{
        background: {c.page_surface};
        border: 1px solid {c.page_edge};
        border-radius: {s.xl}px;
    }}

    QLabel#pdfPageTitle {{
        color: {c.text_secondary};
        font-size: {t.supporting}px;
    }}

    QLabel#pdfPageImage {{
        background: {c.page_surface};
        border: 1px solid {c.outline_variant};
        border-radius: {s.md}px;
    }}

    QFrame#AiSidebarRail {{
        background: {c.surface};
        border: 1px solid {c.outline_variant};
        border-radius: {s.lg}px;
    }}

    QFrame#AiSidebarContent {{
        background: {c.surface};
        border: 1px solid {c.outline_variant};
        border-radius: {s.xl}px;
    }}

    QLabel#EmptyState {{
        color: {c.text_secondary};
        font-size: {t.supporting}px;
        padding: {sp.s16}px;
        background: {c.surface_variant};
        border: 1px dashed {c.outline};
        border-radius: {s.lg}px;
    }}

    QLabel#ErrorState {{
        color: {c.error};
        font-size: {t.supporting}px;
    }}

    QFrame#translatedReaderOuter {{
        background: {c.surface_container};
        border: 1px solid {c.outline_variant};
        border-radius: {s.lg}px;
    }}

    QFrame#translatedPageContainer {{
        background: transparent;
        border: none;
    }}

    QFrame#translatedPageSurface {{
        background: {c.page_surface};
        border: 1px solid {c.page_edge};
        border-radius: {s.xl}px;
    }}

    QFrame#translatedInfoStrip {{
        background: {c.surface_variant};
        border: 1px solid {c.outline_variant};
        border-radius: {s.md}px;
    }}

    QFrame#translatedStatusBanner {{
        background: {c.surface_variant};
        border: 1px solid {c.outline_variant};
        border-radius: {s.md}px;
    }}

    QFrame#translatedStatusBanner[status="translating"] {{
        background: {c.primary_container};
        border-color: {c.primary};
    }}

    QFrame#translatedStatusBanner[status="partial"] {{
        background: {c.surface_variant};
        border-color: {c.primary};
    }}

    QFrame#translatedStatusBanner[status="failed"] {{
        background: #FDECEC;
        border-color: {c.error};
    }}

    QFrame#translatedStatusBanner[status="empty"] {{
        background: {c.surface_variant};
        border-style: dashed;
    }}

    QFrame#translatedSectionCard {{
        background: {c.surface_variant};
        border: 1px solid {c.outline_variant};
        border-radius: {s.md}px;
    }}

    QLabel#translatedPageMeta {{
        color: {c.text_tertiary};
        font-size: {t.doc_small}px;
    }}

    QLabel#translatedDocTitle {{
        color: {c.text_primary};
        font-size: {t.doc_title}px;
        font-weight: 700;
    }}

    QLabel#translatedOriginalTitle {{
        color: {c.text_secondary};
        font-size: {t.body}px;
        padding-bottom: {sp.s4}px;
    }}

    QLabel#translatedMetaLine {{
        color: {c.text_secondary};
        font-size: {t.doc_small}px;
    }}

    QLabel#translatedStatusTitle {{
        color: {c.text_primary};
        font-size: {t.body}px;
        font-weight: 700;
    }}

    QLabel#translatedStatusBody {{
        color: {c.text_secondary};
        font-size: {t.supporting}px;
    }}

    QLabel#translatedSectionTitle {{
        color: {c.text_secondary};
        font-size: {t.supporting}px;
        font-weight: 700;
        letter-spacing: 0.5px;
    }}

    QLabel#translatedParagraph {{
        color: {c.text_primary};
        font-size: {t.doc_body}px;
        padding: 2px 0 8px 0;
    }}

    QLabel#translatedParagraph[paragraphRole="meta"] {{
        color: {c.text_secondary};
        font-size: {t.supporting}px;
    }}

    QLabel#translatedParagraph[paragraphRole="references"] {{
        color: {c.text_secondary};
        font-size: {t.doc_small}px;
    }}

    QLabel#translatedParagraph[paragraphRole="formula"] {{
        color: {c.warning};
    }}

    QLabel#translatedHeadingBlock {{
        color: {c.text_primary};
        font-size: 18px;
        font-weight: 700;
        padding-top: {sp.s12}px;
        padding-bottom: {sp.s4}px;
    }}

    QFrame#translationCard {{
        background: {c.surface};
        border: 1px solid {c.outline_variant};
        border-radius: {s.lg}px;
    }}

    QLabel#translationCardMeta {{
        color: {c.text_secondary};
        font-size: {t.supporting}px;
    }}

    QLabel#translationCardTitle {{
        color: {c.text_primary};
        font-size: {t.body}px;
        font-weight: 600;
    }}

    QFrame#aiResultCard {{
        background: {c.surface};
        border: 1px solid {c.outline_variant};
        border-radius: {s.lg}px;
    }}

    QLabel#aiResultTitle {{
        color: {c.text_primary};
        font-size: {t.subtitle}px;
        font-weight: 700;
    }}

    QLabel#AiGeneratedChip {{
        color: {c.on_primary_container};
        background: {c.primary_container};
        border-radius: {s.sm}px;
        padding: {sp.s4}px {sp.s8}px;
        font-size: {t.label}px;
    }}

    QFrame#chatBubbleUser {{
        background: {c.primary_container};
        border: 1px solid {c.primary};
        border-radius: {s.lg}px;
    }}

    QFrame#chatBubbleAI {{
        background: {c.surface};
        border: 1px solid {c.outline_variant};
        border-radius: {s.lg}px;
    }}

    QLabel#chatBubbleTitle {{
        color: {c.text_primary};
        font-size: {t.supporting}px;
        font-weight: 700;
    }}

    QWidget#Snackbar {{
        background: {c.text_primary};
        border-radius: {s.md}px;
    }}

    QLabel#SnackbarText {{
        color: {c.on_primary};
        padding: {sp.s8}px {sp.s12}px;
    }}
    """


def apply_elevation(widget: QWidget, level: str = "card") -> None:
    effect = QGraphicsDropShadowEffect(widget)
    if level == "top_bar":
        effect.setBlurRadius(24)
        effect.setOffset(0, 2)
        effect.setColor(QColor(16, 24, 40, 28))
    elif level == "dialog":
        effect.setBlurRadius(34)
        effect.setOffset(0, 7)
        effect.setColor(QColor(16, 24, 40, 52))
    elif level == "floating":
        effect.setBlurRadius(40)
        effect.setOffset(0, 10)
        effect.setColor(QColor(16, 24, 40, 60))
    else:
        effect.setBlurRadius(28)
        effect.setOffset(0, 6)
        effect.setColor(QColor(16, 24, 40, 30))
    widget.setGraphicsEffect(effect)
