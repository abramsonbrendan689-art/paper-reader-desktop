from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from app.core.config import mask_secret
from app.models.settings import AppSettings


class SettingsDialog(QDialog):
    def __init__(
        self,
        settings: AppSettings,
        provider_statuses: dict[str, tuple[bool, str]] | None = None,
        deepseek_env: dict[str, str] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.resize(760, 620)
        self._settings = settings
        self._provider_statuses = provider_statuses or {}
        self._deepseek_env = deepseek_env or {}

        self._build_ui()
        self._load_values()
        self._render_status_summary()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        status_group = QGroupBox("Provider 状态")
        status_layout = QVBoxLayout(status_group)
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        status_layout.addWidget(self.status_label)
        layout.addWidget(status_group)

        env_group = QGroupBox("DeepSeek 持久配置（保存到项目根目录 .env）")
        env_layout = QFormLayout(env_group)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("填写后保存到项目根目录 .env")
        self.show_key_checkbox = QCheckBox("显示 API Key")

        self.base_url_edit = QLineEdit()
        self.base_url_edit.setPlaceholderText("https://api.deepseek.com")

        self.default_model_env_edit = QLineEdit()
        self.default_model_env_edit.setPlaceholderText("deepseek-chat")

        self.reasoning_model_env_edit = QLineEdit()
        self.reasoning_model_env_edit.setPlaceholderText("deepseek-reasoner")

        self.persist_env_checkbox = QCheckBox("保存 DeepSeek 配置到项目根目录 .env")
        self.persist_env_checkbox.setChecked(True)

        self.env_hint_label = QLabel(
            "程序只读取当前项目根目录的 .env。保存后，下次重启会自动生效。"
        )
        self.env_hint_label.setWordWrap(True)

        env_layout.addRow("DEEPSEEK_API_KEY", self.api_key_edit)
        env_layout.addRow("", self.show_key_checkbox)
        env_layout.addRow("DEEPSEEK_BASE_URL", self.base_url_edit)
        env_layout.addRow("DEEPSEEK_MODEL", self.default_model_env_edit)
        env_layout.addRow("DEEPSEEK_REASONING_MODEL", self.reasoning_model_env_edit)
        env_layout.addRow("", self.persist_env_checkbox)
        env_layout.addRow("", self.env_hint_label)
        layout.addWidget(env_group)

        form_group = QGroupBox("应用配置")
        form = QFormLayout(form_group)

        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["deepseek"])

        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("deepseek-chat")

        self.reasoning_checkbox = QCheckBox("深度分析使用 deepseek-reasoner")

        self.storage_dir_edit = QLineEdit()
        self.cache_dir_edit = QLineEdit()
        self.db_path_edit = QLineEdit()
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["light", "dark"])

        form.addRow("默认 Provider", self.provider_combo)
        form.addRow("当前默认模型", self.model_edit)
        form.addRow("高级开关", self.reasoning_checkbox)
        form.addRow("存储目录", self.storage_dir_edit)
        form.addRow("缓存目录", self.cache_dir_edit)
        form.addRow("数据库路径", self.db_path_edit)
        form.addRow("主题", self.theme_combo)
        layout.addWidget(form_group)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.show_key_checkbox.toggled.connect(self._toggle_key_visibility)
        self.api_key_edit.textChanged.connect(lambda _: self._render_status_summary())

    def _render_status_summary(self) -> None:
        ok, msg = self._provider_statuses.get("deepseek", (False, "状态未知"))
        state = "可用" if ok else "不可用"
        masked = mask_secret(self.api_key_edit.text())
        self.status_label.setText(f"- deepseek: {state} | {msg}\n- API Key: {masked}")

    def _load_values(self) -> None:
        self.provider_combo.setCurrentText("deepseek")
        self.model_edit.setText(self._settings.model_name or "deepseek-chat")
        self.reasoning_checkbox.setChecked(bool(self._settings.use_reasoning_for_analysis))
        self.storage_dir_edit.setText(self._settings.storage_dir)
        self.cache_dir_edit.setText(self._settings.cache_dir)
        self.db_path_edit.setText(self._settings.db_path)
        self.theme_combo.setCurrentText(self._settings.ui_theme or "light")

        self.api_key_edit.setText(self._deepseek_env.get("api_key", ""))
        self.base_url_edit.setText(self._deepseek_env.get("base_url", "https://api.deepseek.com"))
        self.default_model_env_edit.setText(
            self._deepseek_env.get("model", self._settings.model_name or "deepseek-chat")
        )
        self.reasoning_model_env_edit.setText(
            self._deepseek_env.get("reasoning_model", "deepseek-reasoner")
        )

    def _toggle_key_visibility(self, checked: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        self.api_key_edit.setEchoMode(mode)

    def should_persist_env(self) -> bool:
        return self.persist_env_checkbox.isChecked()

    def to_env_updates(self) -> dict[str, str]:
        return {
            "DEFAULT_PROVIDER": "deepseek",
            "DEEPSEEK_API_KEY": self.api_key_edit.text().strip(),
            "DEEPSEEK_BASE_URL": self.base_url_edit.text().strip() or "https://api.deepseek.com",
            "DEEPSEEK_MODEL": self.default_model_env_edit.text().strip() or "deepseek-chat",
            "DEEPSEEK_REASONING_MODEL": self.reasoning_model_env_edit.text().strip()
            or "deepseek-reasoner",
        }

    def to_settings(self) -> AppSettings:
        return AppSettings(
            id=1,
            default_provider="deepseek",
            model_name=self.model_edit.text().strip() or "deepseek-chat",
            use_reasoning_for_analysis=self.reasoning_checkbox.isChecked(),
            storage_dir=self.storage_dir_edit.text().strip(),
            cache_dir=self.cache_dir_edit.text().strip(),
            db_path=self.db_path_edit.text().strip(),
            ui_theme=self.theme_combo.currentText().strip(),
        )
