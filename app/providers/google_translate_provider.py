from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from google.api_core.exceptions import GoogleAPICallError
from google.cloud import translate_v3

from app.core.logging import logger
from app.providers.base_provider import BaseProvider


class GoogleCloudTranslateProvider(BaseProvider):
    name = "google_cloud"

    def __init__(
        self,
        project_id: str,
        location: str = "us-central1",
        credentials_path: str = "",
        model: str = "general/translation-llm",
        glossary: str = "",
        timeout: int = 60,
        max_batch_items: int = 24,
        max_batch_chars: int = 12000,
    ):
        self.project_id = (project_id or "").strip()
        self.location = (location or "us-central1").strip()
        self.credentials_path = (credentials_path or "").strip()
        self.model = (model or "general/translation-llm").strip()
        self.glossary = (glossary or "").strip()
        self.timeout = timeout
        self.max_batch_items = max_batch_items
        self.max_batch_chars = max_batch_chars

        self.client: translate_v3.TranslationServiceClient | None = None
        self._available = False
        self._unavailable_reason = ""

        self._initialize_client()

    def _initialize_client(self) -> None:
        if not self.project_id:
            self._set_unavailable("Google Cloud Translation 未配置：缺少 GOOGLE_CLOUD_PROJECT")
            return

        if self.credentials_path:
            cred_path = Path(self.credentials_path)
            if not cred_path.exists():
                self._set_unavailable(
                    f"Google Cloud Translation 未配置：凭证文件不存在 ({cred_path})"
                )
                return
            os.environ.setdefault("GOOGLE_APPLICATION_CREDENTIALS", str(cred_path))
        else:
            # This project requires explicit env-based credentials configuration.
            self._set_unavailable("Google Cloud Translation 未配置：缺少 GOOGLE_APPLICATION_CREDENTIALS")
            return

        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", self.project_id)

        try:
            self.client = translate_v3.TranslationServiceClient()
            self._available = True
            self._unavailable_reason = ""
        except Exception as exc:  # noqa: BLE001
            self._set_unavailable(f"Google Cloud Translation 初始化失败: {exc}")

    def _set_unavailable(self, reason: str) -> None:
        self._available = False
        self._unavailable_reason = reason
        logger.warning(reason)

    def is_configured(self) -> bool:
        return self._available and self.client is not None

    def is_available(self) -> bool:
        return self.is_configured()

    def availability_reason(self) -> str:
        return self._unavailable_reason

    @property
    def parent(self) -> str:
        return f"projects/{self.project_id}/locations/{self.location}"

    def _build_model_path(self, custom_model: str | None = None) -> str:
        model_value = (custom_model or self.model or "general/translation-llm").strip()
        if model_value.startswith("projects/"):
            return model_value
        if model_value.startswith("models/"):
            return f"projects/{self.project_id}/locations/{self.location}/{model_value}"
        return f"projects/{self.project_id}/locations/{self.location}/models/{model_value}"

    def _build_glossary_path(self, glossary_value: str | None = None) -> str | None:
        value = (glossary_value if glossary_value is not None else self.glossary).strip()
        if not value:
            return None
        if value.startswith("projects/"):
            return value
        if value.startswith("glossaries/"):
            return f"projects/{self.project_id}/locations/{self.location}/{value}"
        return f"projects/{self.project_id}/locations/{self.location}/glossaries/{value}"

    def test_connection(self) -> tuple[bool, str]:
        if not self.is_available() or not self.client:
            return False, self.availability_reason() or "Google Cloud Translation unavailable"
        try:
            self.client.get_supported_languages(
                request={
                    "parent": self.parent,
                    "display_language_code": "en",
                },
                timeout=min(self.timeout, 5),
            )
            return True, "Google Cloud Translation 可用"
        except Exception as exc:  # noqa: BLE001
            return False, f"Google Cloud Translation 连通性检查失败: {exc}"

    def translate(
        self,
        text: str,
        source_lang: str = "en",
        target_lang: str = "zh",
        options: dict[str, Any] | None = None,
    ) -> str:
        if not text.strip():
            return ""
        block = {
            "text": text,
            "mime_type": (options or {}).get("mime_type", "text/plain"),
            "allow_plain_fallback": True,
        }
        result = self.translate_blocks(
            blocks=[block],
            source_lang=source_lang,
            target_lang=target_lang,
            options=options,
        )
        return result[0] if result else ""

    def translate_blocks(
        self,
        blocks: list[dict[str, Any]],
        source_lang: str = "en",
        target_lang: str = "zh",
        options: dict[str, Any] | None = None,
    ) -> list[str]:
        if not self.is_available() or not self.client:
            raise RuntimeError(self.availability_reason() or "Google Cloud Translation unavailable")

        opts = options or {}
        model_path = self._build_model_path(opts.get("model"))
        glossary_path = self._build_glossary_path(opts.get("glossary"))
        timeout = int(opts.get("timeout", self.timeout))

        output: list[str] = ["" for _ in blocks]
        indexed_blocks = list(enumerate(blocks))

        # Group by mime_type because one API request supports one mime_type.
        mime_groups: dict[str, list[tuple[int, dict[str, Any]]]] = {}
        for idx, block in indexed_blocks:
            mime_type = (block.get("mime_type") or opts.get("mime_type") or "text/plain").strip().lower()
            if mime_type not in {"text/plain", "text/html"}:
                mime_type = "text/plain"
            mime_groups.setdefault(mime_type, []).append((idx, block))

        for mime_type, group in mime_groups.items():
            for batch in self._build_batches(group):
                batch_indexes = [x[0] for x in batch]
                contents = [str(x[1].get("text") or "") for x in batch]
                try:
                    translated = self._translate_contents(
                        contents=contents,
                        mime_type=mime_type,
                        source_lang=source_lang,
                        target_lang=target_lang,
                        model_path=model_path,
                        glossary_path=glossary_path,
                        timeout=timeout,
                    )
                    for local_idx, target_idx in enumerate(batch_indexes):
                        output[target_idx] = translated[local_idx]
                except Exception as exc:  # noqa: BLE001
                    logger.exception(
                        "Google batch translation failed (mime_type={} size={}): {}",
                        mime_type,
                        len(contents),
                        exc,
                    )
                    if mime_type == "text/html":
                        # Fallback to plain text per block, preserving order.
                        for local_idx, (target_idx, block) in enumerate(batch):
                            allow_fallback = bool(block.get("allow_plain_fallback", True))
                            if not allow_fallback:
                                output[target_idx] = f"翻译失败: {exc}"
                                continue
                            try:
                                plain_text = str(block.get("plain_text") or block.get("text") or "")
                                plain_translated = self._translate_contents(
                                    contents=[plain_text],
                                    mime_type="text/plain",
                                    source_lang=source_lang,
                                    target_lang=target_lang,
                                    model_path=model_path,
                                    glossary_path=glossary_path,
                                    timeout=timeout,
                                )
                                output[target_idx] = plain_translated[0] if plain_translated else ""
                            except Exception as fallback_exc:  # noqa: BLE001
                                logger.exception(
                                    "Google plain fallback failed for block {}: {}",
                                    target_idx,
                                    fallback_exc,
                                )
                                output[target_idx] = f"翻译失败: {fallback_exc}"
                    else:
                        for target_idx in batch_indexes:
                            output[target_idx] = f"翻译失败: {exc}"

        return output

    def _build_batches(
        self,
        group: list[tuple[int, dict[str, Any]]],
    ) -> list[list[tuple[int, dict[str, Any]]]]:
        batches: list[list[tuple[int, dict[str, Any]]]] = []
        current: list[tuple[int, dict[str, Any]]] = []
        current_chars = 0

        for item in group:
            text = str(item[1].get("text") or "")
            size = len(text)
            if current and (
                len(current) >= self.max_batch_items or current_chars + size > self.max_batch_chars
            ):
                batches.append(current)
                current = []
                current_chars = 0
            current.append(item)
            current_chars += size

        if current:
            batches.append(current)
        return batches

    def _translate_contents(
        self,
        contents: list[str],
        mime_type: str,
        source_lang: str,
        target_lang: str,
        model_path: str,
        glossary_path: str | None,
        timeout: int,
    ) -> list[str]:
        if not self.client:
            raise RuntimeError("Google Cloud Translation client unavailable")

        request: dict[str, Any] = {
            "parent": self.parent,
            "contents": contents,
            "mime_type": mime_type,
            "source_language_code": source_lang,
            "target_language_code": target_lang,
            "model": model_path,
        }
        if glossary_path:
            request["glossary_config"] = {"glossary": glossary_path}

        try:
            response = self.client.translate_text(request=request, timeout=timeout)
        except GoogleAPICallError as exc:
            raise RuntimeError(f"Google Cloud API 调用失败: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Google Cloud 翻译失败: {exc}") from exc

        if glossary_path and getattr(response, "glossary_translations", None):
            translated = [x.translated_text for x in response.glossary_translations]
        else:
            translated = [x.translated_text for x in response.translations]

        if len(translated) != len(contents):
            raise RuntimeError("Google Cloud 返回结果数量与请求不一致")

        return translated

    def summarize(self, text: str, options: dict[str, Any] | None = None) -> str:
        return "Google Cloud Translation Provider 仅支持翻译。请切换到 OpenAI 或 Gemini 以使用摘要能力。"

    def explain(
        self,
        text: str,
        question: str,
        options: dict[str, Any] | None = None,
    ) -> str:
        return "Google Cloud Translation Provider 仅支持翻译。请切换到 OpenAI 或 Gemini 以使用解释能力。"
