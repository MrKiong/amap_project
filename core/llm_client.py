from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from openai import APIConnectionError, APIError, APITimeoutError, OpenAI

from config.settings import Settings
from core.message import Message
from core.tool_schema import ToolSchema


class LLMConfigurationError(RuntimeError):
    pass


@dataclass
class LLMResponse:
    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


class LLMClient:
    def __init__(self, settings: Settings, timeout_seconds: int = 60):
        self.settings = settings
        self.timeout_seconds = timeout_seconds
        self._client: OpenAI | None = None

    @property
    def is_configured(self) -> bool:
        return self.settings.llm_configured

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolSchema] | None = None,
    ) -> LLMResponse:
        if not self.is_configured:
            raise LLMConfigurationError(
                "OpenAI-compatible LLM is not configured. Set LLM_API_KEY, "
                "LLM_BASE_URL and LLM_MODEL."
            )

        payload: dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": [message.to_openai() for message in messages],
        }
        if tools:
            payload["tools"] = [tool.to_openai_tool(strict=True) for tool in tools]
            payload["tool_choice"] = "auto"

        return await asyncio.to_thread(self._create_chat_completion, payload)

    def _create_chat_completion(self, payload: dict[str, Any]) -> LLMResponse:
        if not self.is_configured:
            raise LLMConfigurationError("OpenAI-compatible LLM is not configured.")

        try:
            completion = self._openai_client().chat.completions.create(**payload)
        except (APIConnectionError, APITimeoutError, APIError) as exc:
            raise RuntimeError(f"LLM request failed: {exc}") from exc

        raw = completion.model_dump(mode="json") if hasattr(completion, "model_dump") else completion
        if not completion.choices:
            raise RuntimeError("LLM response contained no choices.")
        choice = completion.choices[0]
        message = choice.message
        tool_calls = [
            tool_call.model_dump(mode="json") if hasattr(tool_call, "model_dump") else tool_call
            for tool_call in (message.tool_calls or [])
        ]
        return LLMResponse(
            content=message.content or "",
            tool_calls=tool_calls,
            raw=raw,
        )

    def _openai_client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=self.settings.llm_api_key,
                base_url=self.settings.llm_base_url.rstrip("/"),
                timeout=self.timeout_seconds,
            )
        return self._client
