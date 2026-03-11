from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QCloseEvent, QGuiApplication, QResizeEvent
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from app.core.config import save_project_env_values
from app.core.container import AppContainer
from app.core.logging import logger
from app.models.note import Note
from app.models.reading_state import ReadingState
from app.services.translation_service import TranslationResult
from app.ui.dialogs.settings_dialog import SettingsDialog
from app.ui.widgets.ai_reading_panel import AIReadingPanel
from app.ui.widgets.collapsible_ai_sidebar import CollapsibleAISidebar
from app.ui.widgets.deepseek_chat_panel import DeepSeekChatPanel
from app.ui.widgets.paper_library_panel import PaperLibraryPanel
from app.ui.widgets.parallel_reader_widget import ParallelReaderWidget
from app.ui.widgets.reader_topbar import ReaderTopBar
from app.ui.widgets.snackbar import Snackbar
from app.workers.chat_worker import ChatWorker
from app.workers.import_worker import ImportWorker
from app.workers.summarize_worker import SummarizeWorker
from app.workers.translate_worker import TranslateWorker


class MainWindow(QMainWindow):
    def __init__(self, container: AppContainer):
        super().__init__()
        self.container = container

        self.current_paper = None
        self.current_page = 0
        self.current_selected_text = ""
        self._page_blocks_cache: dict[int, list] = {}
        self._threads: list = []
        self._missing_provider_warned = False
        self._pending_scroll_ratio = 0.0
        self._summary_cache: dict[int, str] = {}
        self._ai_titles: dict[SummarizeWorker, str] = {}
        self._translate_worker_count = 0

        self.setWindowTitle("AI 文献双文档对照阅读器")
        self.resize(2048, 1180)
        self.setObjectName("AppRoot")

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self._reading_state_timer = QTimer(self)
        self._reading_state_timer.setSingleShot(True)
        self._reading_state_timer.timeout.connect(self._persist_reading_state)

        self._build_ui()
        self.refresh_paper_list()
        self._show_provider_status()
        QTimer.singleShot(300, self._warn_if_provider_unavailable)

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("AppRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(4, 4, 4, 4)
        root_layout.setSpacing(4)

        self.top_bar = ReaderTopBar()
        root_layout.addWidget(self.top_bar)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(10)

        self.library_panel = PaperLibraryPanel()
        self.parallel_reader = ParallelReaderWidget(self.container.pdf_service)

        self.ai_panel = AIReadingPanel()
        self.chat_panel = DeepSeekChatPanel()
        notes_panel = self._build_notes_panel()
        self.ai_sidebar = CollapsibleAISidebar()
        self.ai_sidebar.set_panels(self.ai_panel, self.chat_panel, notes_panel)
        self.ai_sidebar.set_expanded(False)

        self.main_splitter.addWidget(self.library_panel)
        self.main_splitter.addWidget(self.parallel_reader)
        self.main_splitter.addWidget(self.ai_sidebar)
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setStretchFactor(2, 0)
        self.main_splitter.setSizes([248, 1760, 52])

        root_layout.addWidget(self.main_splitter, 1)
        self.setCentralWidget(root)

        self._bind_events()

    def _build_notes_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        title = QLabel("阅读笔记")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("记录当前页面理解、引文草稿和待办点。")
        subtitle.setObjectName("SectionSupporting")

        self.notes_list = QListWidget()
        self.note_edit = QPlainTextEdit()
        self.note_edit.setPlaceholderText("输入笔记内容（支持多段）")
        self.save_note_btn = QPushButton("保存笔记")
        self.save_note_btn.setObjectName("AppBarButton")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.notes_list, 1)
        layout.addWidget(self.note_edit)
        layout.addWidget(self.save_note_btn)
        return panel

    def _bind_events(self) -> None:
        self.top_bar.import_file_clicked.connect(self.import_files)
        self.top_bar.import_folder_clicked.connect(self.import_folder)
        self.top_bar.search_changed.connect(self.on_search_changed)
        self.top_bar.mode_changed.connect(self.parallel_reader.set_mode)
        self.top_bar.translate_page_clicked.connect(self.translate_current_page)
        self.top_bar.translate_visible_clicked.connect(self.translate_visible_region)
        self.top_bar.zoom_preset_changed.connect(self.parallel_reader.set_zoom_preset)
        self.top_bar.zoom_in_clicked.connect(self.parallel_reader.zoom_in)
        self.top_bar.zoom_out_clicked.connect(self.parallel_reader.zoom_out)
        self.top_bar.page_jump_requested.connect(self.parallel_reader.jump_to_page)
        self.top_bar.ai_sidebar_toggle_clicked.connect(self._toggle_ai_sidebar)
        self.top_bar.sync_toggled.connect(self.parallel_reader.set_sync_enabled)
        self.top_bar.settings_clicked.connect(self.open_settings)

        self.library_panel.search_changed.connect(self.on_search_changed)
        self.library_panel.paper_selected.connect(self.on_paper_selected)

        self.parallel_reader.current_page_changed.connect(self.on_page_changed)
        self.parallel_reader.scroll_ratio_changed.connect(self._on_scroll_ratio_changed)
        self.parallel_reader.selected_text_changed.connect(self._on_selected_text_changed)

        self.ai_panel.action_requested.connect(self._handle_ai_action)
        self.ai_panel.save_note_requested.connect(self._save_ai_result_to_note)
        self.chat_panel.send_requested.connect(self._send_chat_message)
        self.chat_panel.clear_requested.connect(self._clear_chat_session)
        self.save_note_btn.clicked.connect(self.save_note)

    def _toggle_ai_sidebar(self) -> None:
        expanding = not self.ai_sidebar.is_expanded()
        self.ai_sidebar.set_expanded(expanding)
        if expanding:
            self.main_splitter.setSizes([248, max(1100, self.width() - 680), 400])
        else:
            self.main_splitter.setSizes([248, max(1360, self.width() - 300), 52])

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self.width() < 1840 and self.ai_sidebar.is_expanded():
            self.ai_sidebar.set_expanded(False)
            self.main_splitter.setSizes([248, max(1220, self.width() - 300), 52])

    def _show_provider_status(self) -> None:
        default_provider = self.container.translation_service.get_default_provider_name()
        statuses = self.container.translation_service.get_provider_statuses()
        deepseek_ok, deepseek_msg = statuses.get("deepseek", (False, "状态未知"))
        state = "可用" if deepseek_ok else "不可用"

        model_name = self.container.translation_service.get_default_model_name(reasoning=False)
        analysis_mode = "ON" if self.container.translation_service.use_reasoning_for_analysis else "OFF"

        self.status.showMessage(
            f"Provider: {default_provider} | DeepSeek: {state} | 模型: {model_name} | "
            f"深度分析: {analysis_mode} | {deepseek_msg}"
        )

    def _warn_if_provider_unavailable(self) -> None:
        if self._missing_provider_warned:
            return
        statuses = self.container.translation_service.get_provider_statuses()
        ok, msg = statuses.get("deepseek", (False, "DeepSeek 未配置"))
        if ok:
            return

        self._missing_provider_warned = True
        QMessageBox.information(
            self,
            "DeepSeek 未配置",
            "当前未配置 DeepSeek API Key，AI 功能暂不可用。\n"
            "请在 .env 中填写 DEEPSEEK_API_KEY 后重启，或在“设置”中查看状态。\n\n"
            f"详细信息：{msg}",
        )
        Snackbar.show_message(self, "DeepSeek 未配置，AI 功能暂不可用")

    def _ensure_ai_available(self) -> bool:
        statuses = self.container.translation_service.get_provider_statuses()
        ok, msg = statuses.get("deepseek", (False, "DeepSeek 未配置"))
        if ok:
            return True
        QMessageBox.warning(self, "AI 功能不可用", f"DeepSeek 当前不可用：{msg}")
        Snackbar.show_message(self, "DeepSeek 未配置或不可用")
        return False

    def refresh_paper_list(self, keyword: str = "") -> None:
        papers = self.container.library_service.search_papers(keyword)
        self.library_panel.set_papers(papers)

    def on_search_changed(self, text: str) -> None:
        self.refresh_paper_list(text)
        self.top_bar.set_search_text(text)
        self.library_panel.search_edit.blockSignals(True)
        self.library_panel.search_edit.setText(text)
        self.library_panel.search_edit.blockSignals(False)
        if text.strip():
            self.status.showMessage(f"搜索中：{text}")

    def on_paper_selected(self, paper_id: int) -> None:
        paper = self.container.paper_repo.get_by_id(paper_id)
        if not paper:
            return

        self.current_paper = paper
        self.current_page = 0
        self.current_selected_text = ""
        self._page_blocks_cache.clear()

        state = self.container.reading_state_repo.get_by_paper(paper.id)
        initial_page = state.last_page if state else 0
        initial_ratio = state.scroll_ratio if state else 0.0

        self.parallel_reader.load_pdf(
            paper.file_path,
            initial_page=initial_page,
            initial_scroll_ratio=initial_ratio,
        )
        self.top_bar.set_page_info(initial_page, self.parallel_reader.get_page_count())
        self.load_notes()
        self._load_chat_history()

        title = paper.display_name_cn or paper.title or paper.original_filename
        self.status.showMessage(f"已打开文献：{title}")
        Snackbar.show_message(self, f"已打开：{title}")

    def on_page_changed(self, page_number: int) -> None:
        self.current_page = page_number
        self.top_bar.set_page_info(page_number, self.parallel_reader.get_page_count())
        if not self.current_paper:
            return
        blocks = self._get_page_blocks(page_number)
        self.parallel_reader.set_page_blocks(page_number, blocks)
        self._load_cached_translations(page_number)
        self._schedule_save_reading_state()

    def _get_page_blocks(self, page_number: int):
        if page_number in self._page_blocks_cache:
            return self._page_blocks_cache[page_number]
        if not self.current_paper:
            return []
        blocks = self.container.pdf_service.extract_page_blocks(self.current_paper.file_path, page_number)
        self._page_blocks_cache[page_number] = blocks
        return blocks

    def _load_cached_translations(self, page_number: int) -> None:
        if not self.current_paper:
            return
        provider_name = self.container.translation_service.get_default_provider_name()
        cached = self.container.translation_repo.get_page_blocks(
            paper_id=self.current_paper.id,
            page_number=page_number,
            provider_name=provider_name,
        )
        blocks = self._get_page_blocks(page_number)
        if not cached:
            self.parallel_reader.set_page_blocks(page_number, blocks)
            return

        items = [
            TranslationResult(
                page_number=x.page_number,
                block_index=x.block_index,
                source_text=x.source_text,
                translated_text=x.translated_text,
                block_type="cached",
                from_cache=True,
            )
            for x in cached
        ]
        self.parallel_reader.set_page_translations(page_number, blocks, items)

    def _on_scroll_ratio_changed(self, ratio: float) -> None:
        self._pending_scroll_ratio = ratio
        self._schedule_save_reading_state()

    def _schedule_save_reading_state(self) -> None:
        if self.current_paper:
            self._reading_state_timer.start(700)

    def _persist_reading_state(self) -> None:
        if not self.current_paper:
            return
        state = ReadingState(
            paper_id=self.current_paper.id,
            last_page=self.current_page,
            scroll_ratio=self._pending_scroll_ratio,
        )
        self.container.reading_state_repo.upsert(state)

    def _on_selected_text_changed(self, text: str) -> None:
        self.current_selected_text = text or ""

    def import_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "选择 PDF 文件", "", "PDF Files (*.pdf)")
        if paths:
            self._run_import(paths)

    def import_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder:
            self._run_import([folder])

    def _run_import(self, paths: list[str]) -> None:
        worker = ImportWorker(self.container.library_service, paths, self)
        worker.progress.connect(self.status.showMessage)
        worker.error.connect(lambda e: QMessageBox.critical(self, "导入失败", e))
        worker.result_ready.connect(self._on_import_done)
        worker.finished.connect(lambda: self._cleanup_thread(worker))
        self._threads.append(worker)
        worker.start()

    def _on_import_done(self, created: list, errors: list[str]) -> None:
        self.refresh_paper_list(self.library_panel.search_edit.text())
        if errors:
            QMessageBox.warning(self, "导入完成（含错误）", "\n".join(errors[:20]))
        self.status.showMessage(f"导入完成，成功 {len(created)} 篇，失败 {len(errors)} 篇")
        Snackbar.show_message(self, f"导入完成：成功 {len(created)} 篇")

    def _start_translate_worker(self, page_blocks_map: dict[int, list], running_message: str) -> None:
        if not self.current_paper:
            return
        if not self._ensure_ai_available():
            return
        if self._translate_worker_count > 0:
            QMessageBox.information(self, "翻译任务进行中", "已有翻译任务正在执行，请等待完成后再发起新的翻译。")
            return

        worker = TranslateWorker(
            translation_service=self.container.translation_service,
            paper_id=self.current_paper.id,
            page_blocks_map=page_blocks_map,
            parent=self,
        )
        self._translate_worker_count += 1
        self.top_bar.set_button_enabled("translate", False)
        self.top_bar.set_button_enabled("visible", False)

        worker.status.connect(self.status.showMessage)
        worker.block_ready.connect(self._on_translation_block_ready)
        worker.result_ready.connect(self._on_translate_done)
        worker.error.connect(lambda e: QMessageBox.critical(self, "翻译失败", e))
        worker.finished.connect(lambda: self._on_translate_worker_finished(worker))
        self._threads.append(worker)
        self.status.showMessage(running_message)
        worker.start()

    def translate_current_page(self) -> None:
        if not self.current_paper:
            QMessageBox.information(self, "提示", "请先选择文献")
            return
        blocks = self._get_page_blocks(self.current_page)
        if not blocks:
            QMessageBox.information(self, "提示", "当前页无可翻译文本块")
            return
        self._start_translate_worker({self.current_page: blocks}, f"正在翻译第 {self.current_page + 1} 页...")

    def translate_visible_region(self) -> None:
        if not self.current_paper:
            QMessageBox.information(self, "提示", "请先选择文献")
            return
        pages = self.parallel_reader.get_visible_pages()
        if not pages:
            QMessageBox.information(self, "提示", "当前无可视页面")
            return
        page_blocks_map: dict[int, list] = {}
        for page in pages:
            blocks = self._get_page_blocks(page)
            if blocks:
                page_blocks_map[page] = blocks
        if not page_blocks_map:
            QMessageBox.information(self, "提示", "可视区域无可翻译文本")
            return
        self._start_translate_worker(page_blocks_map, f"正在翻译可视区域（{len(page_blocks_map)} 页）...")

    def _on_translation_block_ready(self, result_obj: object) -> None:
        if not isinstance(result_obj, TranslationResult):
            return
        result: TranslationResult = result_obj
        self.parallel_reader.update_translation_result(result)
        self.status.showMessage(
            f"翻译进度：第 {result.page_number + 1} 页 block {result.block_index} 已完成"
        )

    def _on_translate_done(self, results: list[TranslationResult]) -> None:
        _ = results
        if self.current_paper:
            self._load_cached_translations(self.current_page)
        self.status.showMessage("翻译任务完成")
        Snackbar.show_message(self, "翻译完成，译文文档已刷新")

    def translate_selected_text(self) -> None:
        if not self._ensure_ai_available():
            return
        text = self.parallel_reader.get_selected_source_text()
        if not text:
            QMessageBox.information(self, "提示", "请先在译文段落或结构模式中选中文本")
            return
        try:
            translated = self.container.translation_service.translate_text(text)
            content = f"原文：\n{text}\n\n中文翻译：\n{translated}"
            self.ai_panel.add_result_card("选中文本翻译", content)
            self.ai_panel.set_status("已完成选中文本翻译")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "翻译失败", str(exc))

    def explain_selected_text(self) -> None:
        text = self.parallel_reader.get_selected_source_text()
        if not text:
            QMessageBox.information(self, "提示", "请先在译文段落或结构模式中选中文本")
            return
        self._run_ai_worker(
            mode="explain",
            payload={"text": text, "question": "请解释该段落，并说明它在全文中的作用。"},
            title="选中文本解释",
            status_message="正在解释选中文本...",
        )

    def send_selected_to_chat(self) -> None:
        text = self.parallel_reader.get_selected_source_text()
        if not text:
            QMessageBox.information(self, "提示", "请先在译文段落或结构模式中选中文本")
            return
        if not self.ai_sidebar.is_expanded():
            self._toggle_ai_sidebar()
        self.chat_panel.set_input_text(text)
        self.status.showMessage("已将选中文本填入聊天输入框")
        Snackbar.show_message(self, "已发送到聊天输入框")

    def _handle_ai_action(self, action: str) -> None:
        if not self.current_paper:
            QMessageBox.information(self, "提示", "请先选择文献")
            return

        if action == "page":
            blocks = self._get_page_blocks(self.current_page)
            payload = {"blocks": [b.text for b in blocks if b.text.strip()]}
            self._run_ai_worker("page", payload, "当前页摘要", "正在生成当前页摘要...")
            return

        payload = {
            "pdf_path": self.current_paper.file_path,
            "analysis_mode": self.container.translation_service.use_reasoning_for_analysis,
        }
        title_map = {
            "paper": "全文摘要",
            "innovation": "创新点提取",
            "limitation": "局限性提取",
            "method": "方法总结",
            "conclusion": "结论总结",
            "reading_note": "阅读笔记",
        }
        status_map = {
            "paper": "正在生成全文摘要...",
            "innovation": "正在提取创新点...",
            "limitation": "正在提取局限性...",
            "method": "正在总结方法...",
            "conclusion": "正在总结结论...",
            "reading_note": "正在生成阅读笔记...",
        }
        self._run_ai_worker(
            mode=action,
            payload=payload,
            title=title_map.get(action, "AI 结果"),
            status_message=status_map.get(action, "AI 分析中..."),
        )

    def _run_ai_worker(self, mode: str, payload: dict, title: str, status_message: str) -> None:
        if not self.current_paper:
            return
        if not self._ensure_ai_available():
            return
        worker = SummarizeWorker(
            ai_reading_service=self.container.ai_reading_service,
            mode=mode,
            payload=payload,
            parent=self,
        )
        self._ai_titles[worker] = title
        worker.result_ready.connect(lambda content, w=worker: self._on_ai_result(w, content))
        worker.error.connect(lambda e: QMessageBox.critical(self, "AI 任务失败", e))
        worker.finished.connect(lambda w=worker: self._cleanup_ai_worker(w))
        self._threads.append(worker)
        self.ai_panel.set_status(status_message)
        self.status.showMessage(status_message)
        worker.start()

    def _on_ai_result(self, worker: SummarizeWorker, content: str) -> None:
        title = self._ai_titles.get(worker, "AI 结果")
        self.ai_panel.add_result_card(title, content)
        self.ai_panel.set_status(f"{title} 已完成")
        if self.current_paper and title == "全文摘要":
            self._summary_cache[self.current_paper.id] = content

    def _cleanup_ai_worker(self, worker: SummarizeWorker) -> None:
        self._ai_titles.pop(worker, None)
        self._cleanup_thread(worker)

    def summarize_full_paper(self) -> None:
        if not self.current_paper:
            QMessageBox.information(self, "提示", "请先选择文献")
            return
        self._run_ai_worker(
            mode="paper",
            payload={"pdf_path": self.current_paper.file_path},
            title="全文摘要",
            status_message="正在生成全文摘要...",
        )

    def _save_ai_result_to_note(self, content: str) -> None:
        if not self.current_paper:
            return
        note = Note(
            paper_id=self.current_paper.id,
            page_number=self.current_page,
            selected_text=self.current_selected_text,
            note_content=content,
        )
        self.container.note_repo.create(note)
        self.load_notes()
        self.status.showMessage("AI 结果已保存到笔记")

    def _send_chat_message(self, user_message: str, context_mode: str) -> None:
        if not self.current_paper:
            QMessageBox.information(self, "提示", "请先选择文献")
            return
        if not self._ensure_ai_available():
            return

        selected_text = self.parallel_reader.get_selected_source_text()
        translated_text = self.parallel_reader.get_current_page_translated_text()

        try:
            context_text = self.container.chat_service.build_context(
                paper_id=self.current_paper.id,
                pdf_path=self.current_paper.file_path,
                current_page=self.current_page,
                selected_text=selected_text,
                mode=context_mode,
                translated_text=translated_text,
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "上下文构建失败", str(exc))
            return

        history = self.container.chat_service.list_messages(self.current_paper.id)
        history = history[-20:]
        self.chat_panel.append_message("user", user_message)
        self.container.chat_service.save_message(self.current_paper.id, "user", user_message)

        worker = ChatWorker(
            chat_service=self.container.chat_service,
            user_message=user_message,
            history=history,
            context_text=context_text,
            analysis_mode=self.container.translation_service.use_reasoning_for_analysis,
            parent=self,
        )
        worker.result_ready.connect(self._on_chat_reply)
        worker.error.connect(self._on_chat_error)
        worker.finished.connect(lambda: self._cleanup_thread(worker))
        self._threads.append(worker)

        self.chat_panel.set_generating(True)
        self.chat_panel.set_status("DeepSeek 正在生成回复...")
        self.status.showMessage("DeepSeek 正在生成回复...")
        worker.start()

    def _on_chat_reply(self, content: str) -> None:
        if not self.current_paper:
            return
        self.chat_panel.set_generating(False)
        self.chat_panel.append_message("assistant", content)
        self.container.chat_service.save_message(self.current_paper.id, "assistant", content)
        self.chat_panel.set_status("DeepSeek 回复完成")
        self.status.showMessage("聊天回复已生成")

    def _on_chat_error(self, error_text: str) -> None:
        self.chat_panel.set_generating(False)
        QMessageBox.critical(self, "聊天失败", error_text)

    def _load_chat_history(self) -> None:
        if not self.current_paper:
            self.chat_panel.clear_messages()
            return
        messages = self.container.chat_service.list_messages(self.current_paper.id)
        self.chat_panel.load_messages(messages)

    def _clear_chat_session(self) -> None:
        if not self.current_paper:
            return
        self.container.chat_service.clear_messages(self.current_paper.id)
        self.chat_panel.clear_messages()
        self.chat_panel.set_status("当前文献会话已清空")

    def save_note(self) -> None:
        if not self.current_paper:
            QMessageBox.information(self, "提示", "请先选择文献")
            return
        note_content = self.note_edit.toPlainText().strip()
        if not note_content:
            QMessageBox.information(self, "提示", "笔记内容为空")
            return
        selected = self.parallel_reader.get_selected_source_text()
        note = Note(
            paper_id=self.current_paper.id,
            page_number=self.current_page,
            selected_text=selected,
            note_content=note_content,
        )
        self.container.note_repo.create(note)
        self.note_edit.clear()
        self.load_notes()
        self.status.showMessage("笔记已保存")
        Snackbar.show_message(self, "笔记已保存")

    def load_notes(self) -> None:
        self.notes_list.clear()
        if not self.current_paper:
            return
        notes = self.container.note_repo.list_by_paper(self.current_paper.id)
        for note in notes:
            first_line = note.note_content.splitlines()[0] if note.note_content else "(empty)"
            item = QListWidgetItem(f"P{note.page_number + 1}: {first_line[:80]}")
            item.setToolTip(note.note_content)
            self.notes_list.addItem(item)

    def open_settings(self) -> None:
        settings = self.container.settings_repo.get()
        statuses = self.container.translation_service.get_provider_statuses()
        config = self.container.config
        deepseek_env = {
            "api_key": config.deepseek_api_key or "",
            "base_url": config.deepseek_base_url or "https://api.deepseek.com",
            "model": config.deepseek_model or "deepseek-chat",
            "reasoning_model": config.deepseek_reasoning_model or "deepseek-reasoner",
        }

        dialog = SettingsDialog(
            settings,
            provider_statuses=statuses,
            deepseek_env=deepseek_env,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        if dialog.should_persist_env():
            save_project_env_values(dialog.to_env_updates())

        new_settings = dialog.to_settings()
        self.container.settings_repo.update(new_settings)
        self.container.reload_providers()
        self._show_provider_status()
        QMessageBox.information(
            self,
            "设置已保存",
            "设置已保存。\nDeepSeek 配置已写入项目根目录 .env，应用配置已写入数据库。",
        )

    def _cleanup_thread(self, thread) -> None:
        try:
            self._threads.remove(thread)
        except ValueError:
            pass
        logger.debug("Worker finished. Active workers: {}", len(self._threads))

    def _on_translate_worker_finished(self, worker: TranslateWorker) -> None:
        self._translate_worker_count = max(0, self._translate_worker_count - 1)
        if self._translate_worker_count == 0:
            self.top_bar.set_button_enabled("translate", True)
            self.top_bar.set_button_enabled("visible", True)
        self._cleanup_thread(worker)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._reading_state_timer.stop()
        try:
            self._persist_reading_state()
        except Exception:  # noqa: BLE001
            pass

        for thread in list(self._threads):
            try:
                thread.requestInterruption()
            except Exception:  # noqa: BLE001
                pass
        for thread in list(self._threads):
            try:
                if thread.isRunning() and not thread.wait(1500):
                    thread.terminate()
                    thread.wait(500)
            except Exception:  # noqa: BLE001
                pass

        super().closeEvent(event)
