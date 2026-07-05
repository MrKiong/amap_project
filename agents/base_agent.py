from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from core.message import Message
from core.tool_schema import ToolSchema


class BaseAgent(ABC):
    name: str

    @abstractmethod
    async def build_system_prompt(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def build_context(self, user_input: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def get_available_tools(self) -> list[ToolSchema]:
        raise NotImplementedError

    async def build_external_context(
        self,
        user_input: str,
        context: dict[str, Any],
        mcp_client: Any,
    ) -> dict[str, Any]:
        return {}

    async def should_expose_mcp_tools(self) -> bool:
        return False

    async def should_finish(self, messages: list[Message]) -> bool:
        return bool(messages and messages[-1].role == "assistant" and messages[-1].content.strip())

    async def fallback_response(
        self,
        user_input: str,
        context: dict[str, Any],
        tool_results: list[dict[str, Any]] | None = None,
    ) -> str:
        return "当前 LLM 未配置，无法生成 Agent 回复。"
