from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from agents.food_agent.agent import FoodAgent
from agents.food_agent.memory import FoodMemory
from config.settings import Settings
from core.agent_loop import AgentLoop
from core.llm_client import LLMClient, LLMResponse
from core.mcp_client import MCPClient


class AgentLoopTest(unittest.TestCase):
    def test_llm_not_configured_returns_message_without_mcp_lookup(self) -> None:
        class FailingMCPClient(MCPClient):
            async def list_tools(self) -> list[dict]:
                raise AssertionError("MCP lookup should be skipped when LLM is not configured")

            async def call_tool(self, tool_name: str, arguments: dict) -> dict:
                raise AssertionError("MCP lookup should be skipped when LLM is not configured")

        async def run_case() -> str:
            with tempfile.TemporaryDirectory() as temp_dir:
                settings = Settings(
                    log_level="INFO",
                    llm_api_key="",
                    llm_base_url="",
                    llm_model="test-model",
                    amap_mcp_mode="disabled",
                    amap_mcp_url="",
                    amap_maps_api_key="",
                    database_url=f"sqlite:///{Path(temp_dir) / 'memory.sqlite'}",
                )
                memory = FoodMemory(settings.database_path)
                agent_loop = AgentLoop(
                    agent=FoodAgent(memory),
                    llm_client=LLMClient(settings),
                    mcp_client=FailingMCPClient(settings),
                )
                return await agent_loop.run("明天中午我在国典华园附近，一个人，预算100，不想吃太辣")

        answer = asyncio.run(run_case())
        self.assertIn("当前 LLM 未配置", answer)
        self.assertIn("LLM_API_KEY", answer)
        self.assertNotIn("首推", answer)

    def test_llm_request_failure_does_not_use_rule_recommendation(self) -> None:
        class FailingLLMClient(LLMClient):
            async def chat(self, messages, tools=None):  # type: ignore[no-untyped-def]
                raise RuntimeError("bad model")

        async def run_case() -> str:
            with tempfile.TemporaryDirectory() as temp_dir:
                settings = Settings(
                    log_level="INFO",
                    llm_api_key="x",
                    llm_base_url="https://example.invalid/v1",
                    llm_model="bad-model",
                    amap_mcp_mode="disabled",
                    amap_mcp_url="",
                    amap_maps_api_key="",
                    database_url=f"sqlite:///{Path(temp_dir) / 'memory.sqlite'}",
                )
                memory = FoodMemory(settings.database_path)
                agent_loop = AgentLoop(
                    agent=FoodAgent(memory),
                    llm_client=FailingLLMClient(settings),
                    mcp_client=MCPClient(settings),
                )
                return await agent_loop.run("明天中午国典华园附近，一个人，预算100，不想吃辣")

        answer = asyncio.run(run_case())
        self.assertIn("LLM 调用失败", answer)
        self.assertIn("无法生成餐饮推荐", answer)
        self.assertIn("bad model", answer)
        self.assertNotIn("首推", answer)

    def test_agent_loop_exposes_only_food_agent_allowed_mcp_tools(self) -> None:
        class FakeMCPClient(MCPClient):
            async def list_tools(self) -> list[dict]:
                return [
                    {
                        "name": "maps_geo",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                    {
                        "name": "maps_around_search",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                    {
                        "name": "maps_search_detail",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                    {
                        "name": "maps_direction_driving",
                        "inputSchema": {"type": "object", "properties": {}},
                    },
                ]

            async def call_tool(self, tool_name: str, arguments: dict) -> dict:
                raise AssertionError("LLM should decide when to call tools; this test only inspects exposed schemas")

        class CapturingLLMClient(LLMClient):
            def __init__(self, settings: Settings):
                super().__init__(settings)
                self.last_user_content = ""
                self.last_messages = []
                self.tool_names: list[str] | None = None

            async def chat(self, messages, tools=None):  # type: ignore[no-untyped-def]
                self.last_user_content = messages[-1].content
                self.last_messages = messages
                self.tool_names = [tool.name for tool in tools or []]
                return LLMResponse(content="ok")

        async def run_case() -> tuple[str, list, list[str] | None]:
            with tempfile.TemporaryDirectory() as temp_dir:
                settings = Settings(
                    log_level="INFO",
                    llm_api_key="x",
                    llm_base_url="https://example.invalid/v1",
                    llm_model="test-model",
                    amap_mcp_mode="streamable_http",
                    amap_mcp_url="https://mcp.amap.com/mcp",
                    amap_maps_api_key="test-key",
                    database_url=f"sqlite:///{Path(temp_dir) / 'memory.sqlite'}",
                )
                memory = FoodMemory(settings.database_path)
                llm_client = CapturingLLMClient(settings)
                agent_loop = AgentLoop(
                    agent=FoodAgent(memory),
                    llm_client=llm_client,
                    mcp_client=FakeMCPClient(settings),
                )
                await agent_loop.run("国典华园附近吃什么")
                return llm_client.last_user_content, llm_client.last_messages, llm_client.tool_names

        last_user_content, last_messages, tool_names = asyncio.run(run_case())

        self.assertEqual(tool_names, ["maps_geo", "maps_around_search", "maps_search_detail"])
        self.assertNotIn("restaurant_search", last_user_content)
        self.assertEqual(last_user_content, "国典华园附近吃什么")
        self.assertIn("tool_policy", last_messages[1].content)

    def test_agent_loop_runs_openai_style_tool_call_roundtrip(self) -> None:
        class ToolCallingLLMClient(LLMClient):
            def __init__(self, settings: Settings):
                super().__init__(settings)
                self.calls = 0
                self.saw_tool_result = False

            async def chat(self, messages, tools=None):  # type: ignore[no-untyped-def]
                self.calls += 1
                if self.calls == 1:
                    return LLMResponse(
                        content="",
                        tool_calls=[
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "maps_geo",
                                    "arguments": '{"address":"百子湾地铁站","city":null}',
                                },
                            }
                        ],
                    )
                self.saw_tool_result = any(message.role == "tool" for message in messages)
                return LLMResponse(content="ok")

        class CapturingMCPClient(MCPClient):
            def __init__(self, settings: Settings):
                super().__init__(settings)
                self.last_tool_name = ""
                self.last_arguments = {}

            async def list_tools(self) -> list[dict]:
                return [
                    {
                        "name": "maps_geo",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "address": {"type": "string"},
                                "city": {"type": "string"},
                            },
                            "required": ["address"],
                        },
                    }
                ]

            async def call_tool(self, tool_name: str, arguments: dict) -> dict:
                self.last_tool_name = tool_name
                self.last_arguments = arguments
                return {"content": {"location": "116.0,39.0"}}

        async def run_case() -> tuple[str, ToolCallingLLMClient, CapturingMCPClient, list]:
            with tempfile.TemporaryDirectory() as temp_dir:
                settings = Settings(
                    log_level="INFO",
                    llm_api_key="x",
                    llm_base_url="https://example.invalid/v1",
                    llm_model="test-model",
                    amap_mcp_mode="streamable_http",
                    amap_mcp_url="https://mcp.amap.com/mcp",
                    amap_maps_api_key="test-key",
                    database_url=f"sqlite:///{Path(temp_dir) / 'memory.sqlite'}",
                )
                memory = FoodMemory(settings.database_path)
                llm_client = ToolCallingLLMClient(settings)
                mcp_client = CapturingMCPClient(settings)
                agent_loop = AgentLoop(
                    agent=FoodAgent(memory),
                    llm_client=llm_client,
                    mcp_client=mcp_client,
                )
                answer = await agent_loop.run("公司附近吃什么")
                return answer, llm_client, mcp_client, agent_loop.messages

        answer, llm_client, mcp_client, history = asyncio.run(run_case())

        self.assertEqual(answer, "ok")
        self.assertTrue(llm_client.saw_tool_result)
        self.assertEqual(mcp_client.last_tool_name, "maps_geo")
        self.assertEqual(mcp_client.last_arguments, {"address": "百子湾地铁站"})
        self.assertEqual([message.role for message in history], ["user", "assistant"])

    def test_agent_loop_trims_message_history(self) -> None:
        class CapturingLLMClient(LLMClient):
            async def chat(self, messages, tools=None):  # type: ignore[no-untyped-def]
                return LLMResponse(content="ok")

        async def run_case() -> list:
            with tempfile.TemporaryDirectory() as temp_dir:
                settings = Settings(
                    log_level="INFO",
                    llm_api_key="x",
                    llm_base_url="https://example.invalid/v1",
                    llm_model="test-model",
                    amap_mcp_mode="disabled",
                    amap_mcp_url="",
                    amap_maps_api_key="",
                    database_url=f"sqlite:///{Path(temp_dir) / 'memory.sqlite'}",
                )
                memory = FoodMemory(settings.database_path)
                agent_loop = AgentLoop(
                    agent=FoodAgent(memory),
                    llm_client=CapturingLLMClient(settings),
                    mcp_client=MCPClient(settings),
                    max_message_history=4,
                )
                for index in range(6):
                    await agent_loop.run(f"第{index}轮，国典华园附近吃什么")
                return agent_loop.messages

        messages = asyncio.run(run_case())

        self.assertLessEqual(len(messages), 5)
        self.assertLessEqual(len(messages), 4)
        self.assertNotIn("system", [message.role for message in messages])
