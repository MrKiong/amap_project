from __future__ import annotations

import json
import logging
import time
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
        max_message_history: int = 12,
    ):
        self.agent = agent
        self.llm_client = llm_client
        self.mcp_client = mcp_client
        self.max_tool_rounds = max_tool_rounds
        self.max_message_history = max_message_history
        self.messages: list[Message] = []

    async def run(self, user_input: str) -> str:
        run_started = time.perf_counter()
        logger.info("AgentLoop run start: agent=%s", self.agent.name)
        if not self.llm_client.is_configured:
            logger.info("AgentLoop LLM not configured; skipped agent context and MCP lookup")
            return "当前 LLM 未配置，无法生成餐饮推荐。请先配置 DEEPSEEK_API_KEY、DEEPSEEK_BASE_URL 和 DEEPSEEK_MODEL。"

        started = time.perf_counter()
        context = await self.agent.build_context(user_input)
        logger.info("AgentLoop build_context done: elapsed_ms=%s", elapsed_ms(started))

        started = time.perf_counter()
        external_context = await self.agent.build_external_context(user_input, context, self.mcp_client)
        logger.info("AgentLoop build_external_context done: elapsed_ms=%s", elapsed_ms(started))
        if external_context:
            context["external_context"] = external_context

        started = time.perf_counter()
        tools = await self._build_available_tools()
        logger.info("AgentLoop tools ready: count=%s elapsed_ms=%s", len(tools), elapsed_ms(started))
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
        self._trim_messages()

        tool_results: list[dict[str, Any]] = []
        try:
            for round_index in range(self.max_tool_rounds + 1):
                started = time.perf_counter()
                response = await self.llm_client.chat(self.messages, tools=tools)
                logger.info(
                    "AgentLoop LLM round done: round=%s elapsed_ms=%s tool_calls=%s content_chars=%s",
                    round_index + 1,
                    elapsed_ms(started),
                    len(response.tool_calls),
                    len(response.content),
                )
                assistant_message = Message(
                    role="assistant",
                    content=response.content,
                    tool_calls=response.tool_calls,
                )
                self.messages.append(assistant_message)
                self._trim_messages()
                if not response.tool_calls:
                    logger.info("AgentLoop run done: elapsed_ms=%s", elapsed_ms(run_started))
                    return response.content

                for tool_call in response.tool_calls:
                    started = time.perf_counter()
                    tool_result = await self._handle_tool_call(tool_call)
                    logger.info(
                        "AgentLoop tool call done: elapsed_ms=%s tool_call_id=%s",
                        elapsed_ms(started),
                        tool_call.get("id"),
                    )
                    tool_results.append(tool_result)
                    self.messages.append(
                        Message(
                            role="tool",
                            content=json.dumps(tool_result, ensure_ascii=False, default=str),
                            tool_call_id=tool_call.get("id"),
                        )
                    )
                    self._trim_messages()
            logger.info(
                "AgentLoop reached max_tool_rounds=%s; using fallback response with tool_results_count=%s",
                self.max_tool_rounds,
                len(tool_results),
            )
            return await self.agent.fallback_response(user_input, context, tool_results)
        except LLMConfigurationError:
            logger.info("AgentLoop LLM not configured during chat: elapsed_ms=%s", elapsed_ms(run_started))
            return "当前 LLM 未配置，无法生成餐饮推荐。请先配置 DEEPSEEK_API_KEY、DEEPSEEK_BASE_URL 和 DEEPSEEK_MODEL。"
        except RuntimeError as exc:
            logger.info("AgentLoop LLM failed; no rule fallback: elapsed_ms=%s error=%s", elapsed_ms(run_started), exc)
            tool_results = await self._fallback_tool_results(context)
            answer = await self.agent.fallback_response(user_input, context, tool_results)
            return f"LLM 调用失败，无法生成餐饮推荐。\n原因：{exc}\n\n{answer}"

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
            allowed_tool_names = await self.agent.allowed_mcp_tool_names()
            if allowed_tool_names is not None:
                original_count = len(mcp_tools)
                mcp_tools = [
                    tool
                    for tool in mcp_tools
                    if isinstance(tool, dict) and str(tool.get("name")) in allowed_tool_names
                ]
                logger.info(
                    "AgentLoop filtered MCP tools: allowed=%s before=%s after=%s",
                    sorted(allowed_tool_names),
                    original_count,
                    len(mcp_tools),
                )
            tools.extend(ToolSchema.from_mcp_tool(tool) for tool in mcp_tools)
        return tools

    def _trim_messages(self) -> None:
        if self.max_message_history <= 0:
            return
        system_messages = [message for message in self.messages if message.role == "system"][:1]
        non_system_messages = [message for message in self.messages if message.role != "system"]
        if len(non_system_messages) <= self.max_message_history:
            return

        trimmed = non_system_messages[-self.max_message_history :]
        while trimmed and trimmed[0].role == "tool":
            trimmed.pop(0)
        dropped = len(non_system_messages) - len(trimmed)
        self.messages = system_messages + trimmed
        logger.info(
            "AgentLoop message window trimmed: kept_non_system=%s dropped=%s",
            len(trimmed),
            dropped,
        )


def elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
