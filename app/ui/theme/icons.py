from __future__ import annotations

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QStyle

try:
    import qtawesome as qta

    _HAS_QTA = True
except Exception:  # noqa: BLE001
    qta = None
    _HAS_QTA = False


_MDI_ICON_MAP: dict[str, str] = {
    "import_file": "mdi6.file-import-outline",
    "import_folder": "mdi6.folder-open-outline",
    "search": "mdi6.magnify",
    "translate": "mdi6.translate",
    "translate_selected": "mdi6.translate-variant",
    "parallel": "mdi6.view-carousel-outline",
    "summary": "mdi6.text-box-search-outline",
    "chat": "mdi6.chat-processing-outline",
    "settings": "mdi6.cog-outline",
    "copy": "mdi6.content-copy",
    "zoom_in": "mdi6.magnify-plus-outline",
    "zoom_out": "mdi6.magnify-minus-outline",
    "prev": "mdi6.chevron-left",
    "next": "mdi6.chevron-right",
    "notes": "mdi6.notebook-outline",
    "citation": "mdi6.format-quote-open",
    "explain": "mdi6.help-circle-outline",
    "visible": "mdi6.eye-outline",
    "send": "mdi6.send-outline",
    "clear": "mdi6.trash-can-outline",
    "logs": "mdi6.text-box-outline",
}

_FALLBACK_MAP: dict[str, QStyle.StandardPixmap] = {
    "import_file": QStyle.StandardPixmap.SP_DialogOpenButton,
    "import_folder": QStyle.StandardPixmap.SP_DirOpenIcon,
    "search": QStyle.StandardPixmap.SP_FileDialogContentsView,
    "translate": QStyle.StandardPixmap.SP_BrowserReload,
    "translate_selected": QStyle.StandardPixmap.SP_ArrowRight,
    "parallel": QStyle.StandardPixmap.SP_TitleBarUnshadeButton,
    "summary": QStyle.StandardPixmap.SP_FileDialogDetailedView,
    "chat": QStyle.StandardPixmap.SP_MessageBoxInformation,
    "settings": QStyle.StandardPixmap.SP_FileDialogInfoView,
    "copy": QStyle.StandardPixmap.SP_DialogSaveButton,
    "zoom_in": QStyle.StandardPixmap.SP_ArrowUp,
    "zoom_out": QStyle.StandardPixmap.SP_ArrowDown,
    "prev": QStyle.StandardPixmap.SP_ArrowBack,
    "next": QStyle.StandardPixmap.SP_ArrowForward,
    "notes": QStyle.StandardPixmap.SP_FileIcon,
    "citation": QStyle.StandardPixmap.SP_FileLinkIcon,
    "explain": QStyle.StandardPixmap.SP_MessageBoxQuestion,
    "visible": QStyle.StandardPixmap.SP_DialogYesButton,
    "send": QStyle.StandardPixmap.SP_ArrowForward,
    "clear": QStyle.StandardPixmap.SP_DialogDiscardButton,
    "logs": QStyle.StandardPixmap.SP_FileDialogInfoView,
}


def material_icon(name: str, color: str = "#3657C7") -> QIcon:
    icon_key = _MDI_ICON_MAP.get(name, "mdi6.circle-outline")
    if _HAS_QTA and qta is not None:
        try:
            return qta.icon(icon_key, color=color)
        except Exception:  # noqa: BLE001
            pass
    app = QApplication.instance()
    style = app.style() if app else None
    pix = _FALLBACK_MAP.get(name, QStyle.StandardPixmap.SP_FileIcon)
    if style:
        return style.standardIcon(pix)
    return QIcon()
