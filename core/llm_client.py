from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

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
                "DeepSeek/OpenAI-compatible API is not configured. Set DEEPSEEK_API_KEY, "
                "DEEPSEEK_BASE_URL and DEEPSEEK_MODEL."
            )

        payload: dict[str, Any] = {
            "model": self.settings.deepseek_model,
            "messages": [message.to_openai() for message in messages],
        }
        if tools:
            payload["tools"] = [tool.to_openai_tool() for tool in tools]
            payload["tool_choice"] = "auto"

        return await asyncio.to_thread(self._post_chat_completions, payload)

    def _post_chat_completions(self, payload: dict[str, Any]) -> LLMResponse:
        url = self.settings.deepseek_base_url.rstrip("/")
        if not url.endswith("/chat/completions"):
            url = f"{url}/chat/completions"

        request = urllib.request.Request(
            url=url,
            method="POST",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.deepseek_api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM request failed with HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"LLM request failed: {exc.reason}") from exc

        choice = raw.get("choices", [{}])[0]
        message = choice.get("message", {})
        return LLMResponse(
            content=message.get("content") or "",
            tool_calls=message.get("tool_calls") or [],
            raw=raw,
        )
