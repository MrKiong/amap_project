from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agents.food_agent.memory import FoodMemory
from agents.food_agent.agent import FoodAgent
from agents.food_agent.context import USER_PROFILE
from storage.repositories import MealRecord


class FoodMemoryTest(unittest.TestCase):
    def test_add_and_summarize_meal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            memory = FoodMemory(Path(temp_dir) / "memory.sqlite")
            memory.add_meal(
                MealRecord(
                    restaurant_name="测试小馆",
                    cuisine="粤菜",
                    rating=4.5,
                    pros="安静",
                    cons="位置稍远",
                )
            )

            meals = memory.recent_meals()
            self.assertEqual(meals[0]["restaurant_name"], "测试小馆")
            summary = memory.preference_summary()
            self.assertIn("粤菜", summary)
            self.assertIn("安静", summary)

    def test_parse_home_nearby_uses_profile_home_area(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            agent = FoodAgent(FoodMemory(Path(temp_dir) / "memory.sqlite"))

            parsed = agent.parse_request("推荐一些家附近的晚餐吧，可以电动车去就行")

            self.assertEqual(parsed["location"], USER_PROFILE["home_area"])

    def test_extract_candidates_prefers_poi_over_geocode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            agent = FoodAgent(FoodMemory(Path(temp_dir) / "memory.sqlite"))
            tool_results = [
                {
                    "content": [
                        {
                            "type": "text",
                            "text": '{"results":[{"location":"116.410887,39.974779","level":"住宅区"}]}',
                        }
                    ]
                },
                {
                    "content": [
                        {
                            "type": "text",
                            "text": '{"pois":[{"name":"柒号餐厅","address":"胜古中路2号院"}]}',
                        }
                    ]
                },
            ]

            candidates = agent._extract_candidates(tool_results)

            self.assertEqual(candidates[0]["name"], "柒号餐厅")
