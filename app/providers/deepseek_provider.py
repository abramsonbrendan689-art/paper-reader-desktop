from __future__ import annotations

import json
from typing import Any

from openai import APIConnectionError, APIError, AuthenticationError, BadRequestError, OpenAI, RateLimitError

from app.core.logging import logger
from app.prompts.templates import (
    ACADEMIC_TRANSLATION_PROMPT,
    CHAT_SYSTEM_PROMPT,
    CITATION_ASSIST_PROMPT,
    PARAGRAPH_EXPLAIN_PROMPT,
    SUMMARY_PROMPT,
)
from app.providers.base_provider import BaseProvider


class DeepSeekProvider(BaseProvider):
    name = "deepseek"

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str = "deepseek-chat",
        reasoning_model: str = "deepseek-reasoner",
        timeout: int = 60,
    ):
        self.api_key = (api_key or "").strip()
        self.base_url = (base_url or "https://api.deepseek.com").strip()
        self.model = (model or "deepseek-chat").strip()
        self.reasoning_model = (reasoning_model or "deepseek-reasoner").strip()
        self.timeout = timeout
        self.client: OpenAI | None = None
        self._unavailable_reason = ""

        if not self.api_key:
            self._unavailable_reason = "DeepSeek 未配置：缺少 DEEPSEEK_API_KEY"
            return

        try:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=timeout)
        except Exception as exc:  # noqa: BLE001
            self.client = None
            self._unavailable_reason = f"DeepSeek 初始化失败: {exc}"

    def is_available(self) -> bool:
        return self.client is not None and bool(self.api_key)

    def availability_reason(self) -> str:
        return self._unavailable_reason

    def get_model_name(self, reasoning: bool = False) -> str:
        return self.reasoning_model if reasoning else self.model

    def _choose_model(self, options: dict[str, Any] | None = None) -> str:
        opts = options or {}
        if bool(opts.get("reasoning") or opts.get("analysis_mode")):
            return self.reasoning_model
        return self.model

    def _request_chat_completion(self, messages: list[dict[str, str]], options: dict[str, Any] | None = None) -> str:
        if not self.client:
            raise RuntimeError(self._unavailable_reason or "DeepSeek 不可用")

        opts = options or {}
        model_name = self._choose_model(opts)
        temperature = float(opts.get("temperature", 0.2))
        if model_name == self.reasoning_model:
            temperature = 0.3

        cleaned_messages: list[dict[str, str]] = []
        for msg in messages:
            role = (msg.get("role") or "user").strip()
            content = (msg.get("content") or "").strip()
            if role not in {"system", "user", "assistant"}:
                role = "user"
            if not content:
                continue
            cleaned_messages.append({"role": role, "content": content})

        if not cleaned_messages:
            raise RuntimeError("DeepSeek 请求消息为空")

        try:
            resp = self.client.chat.completions.create(
                model=model_name,
                temperature=temperature,
                messages=cleaned_messages,
            )
            if not resp.choices:
                raise RuntimeError("DeepSeek 返回空结果")
            content = (resp.choices[0].message.content or "").strip()
            if not content:
                raise RuntimeError("DeepSeek 返回内容为空")

            # 不保存或传递 reasoning_content，只返回最终 content。
            return content
        except AuthenticationError as exc:
            raise RuntimeError(f"DeepSeek 鉴权失败，请检查 API Key: {exc}") from exc
        except RateLimitError as exc:
            raise RuntimeError(f"DeepSeek 请求频率或额度受限: {exc}") from exc
        except APIConnectionError as exc:
            raise RuntimeError(f"DeepSeek 网络连接失败: {exc}") from exc
        except BadRequestError as exc:
            raise RuntimeError(f"DeepSeek 请求参数错误: {exc}") from exc
        except APIError as exc:
            raise RuntimeError(f"DeepSeek 服务错误: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"DeepSeek 调用失败: {exc}") from exc

    def _chat(self, system_prompt: str, user_content: str, options: dict[str, Any] | None = None) -> str:
        return self._request_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            options=options,
        )

    def chat(
        self,
        messages: list[dict[str, str]],
        options: dict[str, Any] | None = None,
    ) -> str:
        return self._request_chat_completion(messages=messages, options=options)

    def translate(
        self,
        text: str,
        source_lang: str = "en",
        target_lang: str = "zh",
        options: dict[str, Any] | None = None,
    ) -> str:
        if not text.strip():
            return ""
        opts = options or {}
        glossary = opts.get("glossary", "无")
        system_prompt = ACADEMIC_TRANSLATION_PROMPT.format(glossary=glossary)
        user_prompt = f"源语言: {source_lang}\n目标语言: {target_lang}\n\n{text}"
        return self._chat(system_prompt, user_prompt, opts)

    def translate_blocks(
        self,
        blocks: list[dict[str, Any]],
        source_lang: str = "en",
        target_lang: str = "zh",
        options: dict[str, Any] | None = None,
    ) -> list[str]:
        results: list[str] = []
        for block in blocks:
            raw = (block.get("plain_text") or block.get("text") or "").strip()
            if not raw:
                results.append("")
                continue
            try:
                results.append(
                    self.translate(
                        text=raw,
                        source_lang=source_lang,
                        target_lang=target_lang,
                        options=options,
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("DeepSeek block translation failed: {}", exc)
                results.append(f"翻译失败: {exc}")
        return results

    def summarize(self, text: str, options: dict[str, Any] | None = None) -> str:
        return self._chat(SUMMARY_PROMPT, text, options)

    def explain(
        self,
        text: str,
        question: str,
        options: dict[str, Any] | None = None,
    ) -> str:
        user_prompt = f"用户问题：{question}\n\n段落：\n{text}"
        return self._chat(PARAGRAPH_EXPLAIN_PROMPT, user_prompt, options)

    def analyze_paper(self, text: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        analysis_prompt = (
            "请基于论文内容输出 JSON，不要输出额外说明。JSON 字段："
            "background, problem, method, contributions, results, limitations, innovation_points, citation_points。\n"
            f"其中 citation_points 需遵循：{CITATION_ASSIST_PROMPT}\n\n"
            "论文内容：\n" + text
        )
        raw = self._chat(
            "你是严谨的学术论文分析助手。输出必须是 JSON。",
            analysis_prompt,
            options=options,
        )
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.replace("json", "", 1).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {
                "background": "",
                "problem": "",
                "method": "",
                "contributions": "",
                "results": "",
                "limitations": "",
                "innovation_points": raw,
                "citation_points": "",
            }

    def test_connection(self) -> tuple[bool, str]:
        if not self.is_available():
            return False, self.availability_reason() or "DeepSeek 不可用"
        return True, f"DeepSeek 已配置（模型: {self.model}）"

    def build_chat_messages(
        self,
        history: list[dict[str, str]],
        user_message: str,
        context_text: str = "",
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
        if context_text.strip():
            messages.append(
                {
                    "role": "system",
                    "content": f"以下是当前文献上下文，可用于回答：\n{context_text.strip()}",
                }
            )
        messages.extend(history)
        messages.append({"role": "user", "content": user_message.strip()})
        return messages
