from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from agents.food_agent.memory import FoodMemory
from agents.food_agent.agent import FoodAgent
from agents.food_agent.prompts import FOOD_SYSTEM_PROMPT
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
            self.assertIn("system_time", context)
            self.assertEqual(set(context["system_time"]), {"date", "weekday"})
            self.assertIn("current_request", context)
            self.assertEqual(context["user_profile"]["work_area"], "北京市百子湾地铁站")
            self.assertEqual(context["user_profile"]["default_party"]["people_count"], 2)
            self.assertEqual(context["user_profile"]["default_party"]["relationship"], "夫妻")
            self.assertIn("preference_scope", context["user_profile"])
            self.assertIn("dining_scenarios", context["user_profile"])
            self.assertEqual(
                [scenario["name"] for scenario in context["user_profile"]["dining_scenarios"]],
                ["小吃一顿", "吃点好的", "大吃一顿"],
            )
            self.assertIn("budget_notes", context["user_profile"])
            self.assertIn("cuisine_preferences", context["user_profile"])
            self.assertIn("preference_summary", context)
            self.assertIn("dietary_preferences", context)

    def test_food_agent_context_resolves_tonight_as_current_day(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            agent = FoodAgent(FoodMemory(Path(temp_dir) / "memory.sqlite"))

            async def run_case() -> dict:
                return await agent.build_context("帮我推荐今晚公司附近团建，15人，人均200，不需要太商务")

            context = asyncio.run(run_case())
            hints = context["current_request"]["temporal_hints"]

            self.assertEqual(hints["explicit_time_expression"], "今晚")
            self.assertEqual(hints["resolved_date"], context["system_time"]["date"])
            self.assertEqual(hints["resolved_weekday"], context["system_time"]["weekday"])
            self.assertEqual(hints["meal_period"], "晚餐")

    def test_food_agent_allows_only_restaurant_lookup_tools(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            agent = FoodAgent(FoodMemory(Path(temp_dir) / "memory.sqlite"))

            async def run_case() -> tuple[bool, set[str] | None]:
                return await agent.should_expose_mcp_tools(), await agent.allowed_mcp_tool_names()

            expose_tools, allowed_tools = asyncio.run(run_case())

            self.assertTrue(expose_tools)
            self.assertEqual(allowed_tools, {"maps_geo", "maps_around_search", "maps_search_detail"})

    def test_food_prompt_mentions_time_scenarios_and_tool_flow(self) -> None:
        self.assertIn("system_time", FOOD_SYSTEM_PROMPT)
        self.assertIn("current_request", FOOD_SYSTEM_PROMPT)
        self.assertIn("本轮用户输入", FOOD_SYSTEM_PROMPT)
        self.assertIn("小吃一顿", FOOD_SYSTEM_PROMPT)
        self.assertIn("吃点好的", FOOD_SYSTEM_PROMPT)
        self.assertIn("大吃一顿", FOOD_SYSTEM_PROMPT)
        self.assertIn("人均 400", FOOD_SYSTEM_PROMPT)
        self.assertIn("百子湾地铁站", FOOD_SYSTEM_PROMPT)
        self.assertIn("夫妻 2 人", FOOD_SYSTEM_PROMPT)
        self.assertIn("家庭/夫妻用餐偏好", FOOD_SYSTEM_PROMPT)
        self.assertIn("独立判断", FOOD_SYSTEM_PROMPT)
        self.assertIn("maps_geo", FOOD_SYSTEM_PROMPT)
        self.assertIn("麦当劳", FOOD_SYSTEM_PROMPT)
        self.assertNotIn("适合点什么", FOOD_SYSTEM_PROMPT)
        self.assertNotIn("为什么没有推荐某些类型", FOOD_SYSTEM_PROMPT)
