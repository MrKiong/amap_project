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
                "OpenAI-compatible LLM is not configured. Set LLM_API_KEY, "
                "LLM_BASE_URL and LLM_MODEL."
            )

        payload: dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": [message.to_openai() for message in messages],
        }
        if tools:
            payload["tools"] = [tool.to_openai_tool() for tool in tools]
            payload["tool_choice"] = "auto"

        return await asyncio.to_thread(self._post_chat_completions, payload)

    def _post_chat_completions(self, payload: dict[str, Any]) -> LLMResponse:
        if not self.is_configured:
            raise LLMConfigurationError("OpenAI-compatible LLM is not configured.")

        url = self.settings.llm_base_url.rstrip("/")
        if not url.endswith("/chat/completions"):
            url = f"{url}/chat/completions"

        request = urllib.request.Request(
            url=url,
            method="POST",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.llm_api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8", errors="replace")
                try:
                    raw = json.loads(body)
                except json.JSONDecodeError as exc:
                    status = response_status(response)
                    content_type = response.headers.get("Content-Type", "-")
                    preview = body.strip()[:500] or "<empty response body>"
                    raise RuntimeError(
                        "LLM response was not valid JSON: "
                        f"status={status}, content_type={content_type}, body_preview={preview}"
                    ) from exc
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


def response_status(response: Any) -> str:
    status = getattr(response, "status", None)
    if status is not None:
        return str(status)
    getcode = getattr(response, "getcode", None)
    if callable(getcode):
        return str(getcode())
    return "-"
