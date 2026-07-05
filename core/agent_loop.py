from __future__ import annotations

import json
import logging
from typing import Any

from agents.base_agent import BaseAgent
from core.llm_client import LLMClient, LLMConfigurationError
from core.mcp_client import MCPClient
from core.message import Message
from core.tool_schema import ToolSchema


logger = logging.getLogger(__name__)


class AgentLoop:
    def __init__(
        self,
        agent: BaseAgent,
        llm_client: LLMClient,
        mcp_client: MCPClient,
        max_tool_rounds: int = 8,
    ):
        self.agent = agent
        self.llm_client = llm_client
        self.mcp_client = mcp_client
        self.max_tool_rounds = max_tool_rounds
        self.messages: list[Message] = []

    async def run(self, user_input: str) -> str:
        context = await self.agent.build_context(user_input)
        external_context = await self.agent.build_external_context(user_input, context, self.mcp_client)
        if external_context:
            context["external_context"] = external_context
        tools = await self._build_available_tools()
        system_prompt = await self.agent.build_system_prompt()

        if not self.messages:
            self.messages.append(Message(role="system", content=system_prompt))
        self.messages.append(
            Message(
                role="user",
                content=(
                    f"{user_input}\n\n"
                    f"Agent context JSON:\n{json.dumps(context, ensure_ascii=False, default=str)}"
                ),
            )
        )

        tool_results: list[dict[str, Any]] = []
        try:
            for _ in range(self.max_tool_rounds + 1):
                response = await self.llm_client.chat(self.messages, tools=tools)
                assistant_message = Message(
                    role="assistant",
                    content=response.content,
                    tool_calls=response.tool_calls,
                )
                self.messages.append(assistant_message)
                if not response.tool_calls:
                    return response.content

                for tool_call in response.tool_calls:
                    tool_result = await self._handle_tool_call(tool_call)
                    tool_results.append(tool_result)
                    self.messages.append(
                        Message(
                            role="tool",
                            content=json.dumps(tool_result, ensure_ascii=False, default=str),
                            tool_call_id=tool_call.get("id"),
                        )
                    )
            logger.info(
                "AgentLoop reached max_tool_rounds=%s; using fallback response with tool_results_count=%s",
                self.max_tool_rounds,
                len(tool_results),
            )
            return await self.agent.fallback_response(user_input, context, tool_results)
        except LLMConfigurationError:
            tool_results = await self._fallback_tool_results(context)
            return await self.agent.fallback_response(user_input, context, tool_results)
        except RuntimeError as exc:
            tool_results = await self._fallback_tool_results(context)
            answer = await self.agent.fallback_response(user_input, context, tool_results)
            return f"LLM 调用失败，已使用本地降级推荐。\n原因：{exc}\n\n{answer}"

    async def _handle_tool_call(self, tool_call: dict[str, Any]) -> dict[str, Any]:
        function = tool_call.get("function", {})
        tool_name = function.get("name") or tool_call.get("name")
        raw_arguments = function.get("arguments") or tool_call.get("arguments") or "{}"
        if isinstance(raw_arguments, str):
            arguments = json.loads(raw_arguments or "{}")
        else:
            arguments = raw_arguments
        if not tool_name:
            raise ValueError(f"Invalid tool call without name: {tool_call}")
        return await self.mcp_client.call_tool(tool_name, arguments)

    async def _fallback_tool_results(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        return []

    async def _build_available_tools(self) -> list[ToolSchema]:
        tools = list(await self.agent.get_available_tools())
        if await self.agent.should_expose_mcp_tools():
            mcp_tools = await self.mcp_client.list_tools()
            tools.extend(ToolSchema.from_mcp_tool(tool) for tool in mcp_tools)
        return tools
