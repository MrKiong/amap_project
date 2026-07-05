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
    def test_fallback_response_when_llm_not_configured(self) -> None:
        async def run_case() -> str:
            with tempfile.TemporaryDirectory() as temp_dir:
                settings = Settings(
                    log_level="INFO",
                    deepseek_api_key="",
                    deepseek_base_url="",
                    deepseek_model="deepseek-v4",
                    amap_mcp_mode="disabled",
                    amap_mcp_url="",
                    amap_maps_api_key="",
                    database_url=f"sqlite:///{Path(temp_dir) / 'memory.sqlite'}",
                )
                memory = FoodMemory(settings.database_path)
                agent_loop = AgentLoop(
                    agent=FoodAgent(memory),
                    llm_client=LLMClient(settings),
                    mcp_client=MCPClient(settings),
                )
                return await agent_loop.run("明天中午我在国典华园附近，一个人，预算100，不想吃太辣")

        answer = asyncio.run(run_case())
        self.assertIn("首推", answer)
        self.assertIn("不推荐", answer)

    def test_fallback_response_when_llm_request_fails(self) -> None:
        class FailingLLMClient(LLMClient):
            async def chat(self, messages, tools=None):  # type: ignore[no-untyped-def]
                raise RuntimeError("bad model")

        async def run_case() -> str:
            with tempfile.TemporaryDirectory() as temp_dir:
                settings = Settings(
                    log_level="INFO",
                    deepseek_api_key="x",
                    deepseek_base_url="https://example.invalid/v1",
                    deepseek_model="bad-model",
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
        self.assertIn("首推", answer)

    def test_agent_loop_adds_external_context_for_llm(self) -> None:
        class FakeMCPClient(MCPClient):
            async def list_tools(self) -> list[dict]:
                return [
                    {"name": "maps_geo"},
                    {"name": "maps_around_search"},
                    {"name": "maps_search_detail"},
                ]

            async def call_tool(self, tool_name: str, arguments: dict) -> dict:
                if tool_name == "maps_geo":
                    return {
                        "content": [
                            {"type": "text", "text": '{"results":[{"location":"116.410887,39.974779"}]}'}
                        ]
                    }
                if tool_name == "maps_around_search":
                    return {
                        "content": [
                            {"type": "text", "text": '{"pois":[{"id":"poi-1","name":"柒号餐厅","address":"胜古中路"}]}'}
                        ]
                    }
                if tool_name == "maps_search_detail":
                    return {
                        "content": [
                            {"type": "text", "text": '{"id":"poi-1","name":"柒号餐厅","address":"胜古中路"}'}
                        ]
                    }
                raise AssertionError(tool_name)

        class CapturingLLMClient(LLMClient):
            def __init__(self, settings: Settings):
                super().__init__(settings)
                self.last_user_content = ""
                self.tool_names: list[str] | None = None

            async def chat(self, messages, tools=None):  # type: ignore[no-untyped-def]
                self.last_user_content = messages[-1].content
                self.tool_names = [tool.name for tool in tools or []]
                return LLMResponse(content="ok")

        async def run_case() -> tuple[str, list[str] | None]:
            with tempfile.TemporaryDirectory() as temp_dir:
                settings = Settings(
                    log_level="INFO",
                    deepseek_api_key="x",
                    deepseek_base_url="https://example.invalid/v1",
                    deepseek_model="test-model",
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
                return llm_client.last_user_content, llm_client.tool_names

        last_user_content, tool_names = asyncio.run(run_case())

        self.assertEqual(tool_names, [])
        self.assertIn("restaurant_search", last_user_content)
        self.assertIn("柒号餐厅", last_user_content)
