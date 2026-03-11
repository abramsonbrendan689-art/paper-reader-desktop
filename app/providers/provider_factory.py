from __future__ import annotations

from app.core.config import AppConfig
from app.models.settings import AppSettings
from app.providers.base_provider import BaseProvider
from app.providers.deepseek_provider import DeepSeekProvider


class ProviderFactory:
    def __init__(self, config: AppConfig):
        self.config = config

    def create_all(self, settings: AppSettings | None = None) -> dict[str, BaseProvider]:
        default_model = self.config.deepseek_model
        if settings and settings.model_name:
            default_model = settings.model_name.strip() or default_model

        return {
            "deepseek": DeepSeekProvider(
                api_key=self.config.deepseek_api_key,
                base_url=self.config.deepseek_base_url,
                model=default_model,
                reasoning_model=self.config.deepseek_reasoning_model,
                timeout=self.config.request_timeout,
            )
        }
