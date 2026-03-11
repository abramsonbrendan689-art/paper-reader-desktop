from __future__ import annotations

import json
import shutil
from functools import lru_cache
from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel, Field


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ENV_FILE = PROJECT_ROOT / ".env"
PROJECT_ENV_EXAMPLE_FILE = PROJECT_ROOT / ".env.example"

ENV_TO_FIELD = {
    "APP_NAME": "app_name",
    "APP_ENV": "app_env",
    "DEFAULT_PROVIDER": "default_provider",
    "DEEPSEEK_API_KEY": "deepseek_api_key",
    "DEEPSEEK_BASE_URL": "deepseek_base_url",
    "DEEPSEEK_MODEL": "deepseek_model",
    "DEEPSEEK_REASONING_MODEL": "deepseek_reasoning_model",
    "STORAGE_DIR": "storage_dir",
    "CACHE_DIR": "cache_dir",
    "DB_PATH": "db_path",
    "LOG_LEVEL": "log_level",
    "REQUEST_TIMEOUT": "request_timeout",
    "MAX_TEXT_CHUNK": "max_text_chunk",
    "UI_THEME": "ui_theme",
}


DEFAULT_ENV_TEMPLATE = """APP_NAME=Literature Reader
APP_ENV=development
DEFAULT_PROVIDER=deepseek

DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_REASONING_MODEL=deepseek-reasoner

STORAGE_DIR=./storage
CACHE_DIR=./cache
DB_PATH=./data/literature_reader.db
LOG_LEVEL=INFO
REQUEST_TIMEOUT=60
MAX_TEXT_CHUNK=1800
UI_THEME=light
"""


class AppConfig(BaseModel):
    app_name: str = "Literature Reader"
    app_env: str = "development"
    default_provider: str = "deepseek"

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    deepseek_reasoning_model: str = "deepseek-reasoner"

    storage_dir: str = "./storage"
    cache_dir: str = "./cache"
    db_path: str = "./data/literature_reader.db"

    log_level: str = "INFO"
    request_timeout: int = 60
    max_text_chunk: int = Field(default=1800, ge=300, le=12000)
    ui_theme: str = "light"

    @property
    def base_dir(self) -> Path:
        return PROJECT_ROOT

    @property
    def env_file_path(self) -> Path:
        return PROJECT_ENV_FILE

    def resolve_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return (self.base_dir / path).resolve()

    @property
    def storage_dir_path(self) -> Path:
        return self.resolve_path(self.storage_dir)

    @property
    def cache_dir_path(self) -> Path:
        return self.resolve_path(self.cache_dir)

    @property
    def db_path_path(self) -> Path:
        return self.resolve_path(self.db_path)

    @property
    def logs_dir_path(self) -> Path:
        return self.resolve_path("./logs")

    def ensure_directories(self) -> None:
        self.storage_dir_path.mkdir(parents=True, exist_ok=True)
        self.cache_dir_path.mkdir(parents=True, exist_ok=True)
        self.db_path_path.parent.mkdir(parents=True, exist_ok=True)
        self.logs_dir_path.mkdir(parents=True, exist_ok=True)


def ensure_project_env_file() -> Path:
    if PROJECT_ENV_FILE.exists():
        return PROJECT_ENV_FILE

    if PROJECT_ENV_EXAMPLE_FILE.exists():
        shutil.copyfile(PROJECT_ENV_EXAMPLE_FILE, PROJECT_ENV_FILE)
    else:
        PROJECT_ENV_FILE.write_text(DEFAULT_ENV_TEMPLATE, encoding="utf-8")

    return PROJECT_ENV_FILE


def _read_project_env_values() -> dict[str, str]:
    ensure_project_env_file()
    raw = dotenv_values(PROJECT_ENV_FILE)
    data: dict[str, str] = {}
    for env_key, field_name in ENV_TO_FIELD.items():
        if env_key in raw and raw[env_key] is not None:
            data[field_name] = str(raw[env_key])
    return data


def _format_env_value(value: str) -> str:
    text = str(value)
    if not text:
        return ""
    if any(ch in text for ch in [' ', '#', '"', "'"]) or "\n" in text or "\r" in text:
        return json.dumps(text, ensure_ascii=False)
    return text


def save_project_env_values(values: dict[str, str]) -> Path:
    env_path = ensure_project_env_file()
    current_text = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    lines = current_text.splitlines()

    normalized = {str(key).strip(): "" if value is None else str(value) for key, value in values.items()}
    updated_keys: set[str] = set()
    output_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            output_lines.append(line)
            continue

        key = line.split("=", 1)[0].strip()
        if key in normalized:
            output_lines.append(f"{key}={_format_env_value(normalized[key])}")
            updated_keys.add(key)
        else:
            output_lines.append(line)

    if output_lines and output_lines[-1].strip():
        output_lines.append("")

    for key, value in normalized.items():
        if key in updated_keys:
            continue
        output_lines.append(f"{key}={_format_env_value(value)}")

    env_path.write_text("\n".join(output_lines).rstrip() + "\n", encoding="utf-8")
    return env_path


def mask_secret(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return "未配置"
    if len(text) <= 8:
        return "*" * len(text)
    return f"{text[:4]}{'*' * max(4, len(text) - 8)}{text[-4:]}"


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    config = AppConfig.model_validate(_read_project_env_values())
    config.ensure_directories()
    return config


def reload_config() -> AppConfig:
    get_config.cache_clear()
    return get_config()
