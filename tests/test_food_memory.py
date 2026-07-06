from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from agents.food_agent.memory import FoodMemory
from agents.food_agent.agent import FoodAgent
from storage.repositories import PreferenceRecord


class FoodMemoryTest(unittest.TestCase):
    def test_add_and_summarize_preference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory = FoodMemory(Path(temp_dir) / "memory.sqlite")
            memory.add_preference(
                PreferenceRecord(
                    category="scenario",
                    preference="一个人吃饭时偏好安静、出餐稳定的小店",
                    sentiment="like",
                    weight=3,
                )
            )

            preferences = memory.list_preferences()
            self.assertEqual(preferences[0]["category"], "scenario")
            summary = memory.preference_summary()
            self.assertIn("安静", summary)

    def test_food_agent_context_includes_tool_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            agent = FoodAgent(FoodMemory(Path(temp_dir) / "memory.sqlite"))

            async def run_case() -> dict:
                return await agent.build_context("推荐一些家附近的晚餐吧，可以电动车去就行")

            context = asyncio.run(run_case())

            self.assertEqual(
                context["tool_policy"]["available_amap_tools"],
                ["maps_around_search", "maps_geo", "maps_search_detail"],
            )
            self.assertIn("recommended_lookup_flow", context["tool_policy"])
            self.assertIn("preference_summary", context)
            self.assertIn("dietary_preferences", context)

    def test_food_agent_allows_only_restaurant_lookup_tools(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            agent = FoodAgent(FoodMemory(Path(temp_dir) / "memory.sqlite"))

            async def run_case() -> tuple[bool, set[str] | None]:
                return await agent.should_expose_mcp_tools(), await agent.allowed_mcp_tool_names()

            expose_tools, allowed_tools = asyncio.run(run_case())

            self.assertTrue(expose_tools)
            self.assertEqual(allowed_tools, {"maps_geo", "maps_around_search", "maps_search_detail"})
