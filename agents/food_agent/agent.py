from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from agents.base_agent import BaseAgent
from agents.food_agent.context import USER_PROFILE
from agents.food_agent.memory import FoodMemory
from agents.food_agent.prompts import FOOD_SYSTEM_PROMPT
from core.tool_schema import ToolSchema


class FoodAgent(BaseAgent):
    name = "food_agent"
    amap_tool_allowlist = {"maps_geo", "maps_around_search", "maps_search_detail"}

    def __init__(self, memory: FoodMemory):
        self.memory = memory

    async def build_system_prompt(self) -> str:
        profile = json.dumps(USER_PROFILE, ensure_ascii=False, indent=2)
        return f"{FOOD_SYSTEM_PROMPT}\n\n用户静态资料：\n{profile}"

    async def build_context(self, user_input: str) -> dict[str, Any]:
        # This is the compact, agent-owned context injected into the user message.
        # Keep it factual and structured; style and recommendation policy belong in the prompt.
        return {
            "system_time": self._current_time_context(),
            "current_request": {
                "text": user_input,
                "temporal_hints": self._temporal_hints(user_input),
            },
            "user_profile": USER_PROFILE,
            "preference_summary": self.memory.preference_summary(),
            "dietary_preferences": self.memory.list_preferences(limit=12),
            "tool_policy": {
                "available_amap_tools": sorted(self.amap_tool_allowlist),
                "recommended_lookup_flow": (
                    "Use maps_geo to resolve a named place or address into coordinates, then use "
                    "maps_around_search for nearby restaurant candidates. Use maps_search_detail "
                    "only when a candidate POI needs more detail before making a recommendation."
                ),
            },
        }

    async def get_available_tools(self) -> list[ToolSchema]:
        return []

    async def build_external_context(
        self,
        user_input: str,
        context: dict[str, Any],
        mcp_client: Any,
    ) -> dict[str, Any]:
        # Tool use is now delegated to the LLM via filtered function_call schemas.
        # Keep this hook empty unless an agent needs deterministic external context.
        return {}

    async def should_expose_mcp_tools(self) -> bool:
        return True

    async def allowed_mcp_tool_names(self) -> set[str] | None:
        return set(self.amap_tool_allowlist)

    async def fallback_response(
        self,
        user_input: str,
        context: dict[str, Any],
        tool_results: list[dict[str, Any]] | None = None,
    ) -> str:
        # Do not synthesize restaurant recommendations without a model response.
        # Map candidates and regex parsing are supporting evidence for the LLM, not a
        # standalone recommendation policy.
        return "LLM 当前不可用或未能完成回复，因此没有生成餐厅推荐。请检查模型配置或稍后重试。"

    def _current_time_context(self) -> dict[str, str]:
        now = datetime.now()
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        return {
            "date": now.date().isoformat(),
            "weekday": weekdays[now.weekday()],
        }

    def _temporal_hints(self, user_input: str) -> dict[str, str]:
        today = self._current_time_context()
        hints: dict[str, str] = {}
        if "今晚" in user_input or "今天晚上" in user_input:
            hints.update(
                {
                    "explicit_time_expression": "今晚",
                    "resolved_date": today["date"],
                    "resolved_weekday": today["weekday"],
                    "meal_period": "晚餐",
                    "priority": "本轮用户输入明确指定今晚，不要沿用历史对话中的其他日期",
                }
            )
        elif "今天" in user_input:
            hints.update(
                {
                    "explicit_time_expression": "今天",
                    "resolved_date": today["date"],
                    "resolved_weekday": today["weekday"],
                    "priority": "本轮用户输入明确指定今天，不要沿用历史对话中的其他日期",
                }
            )
        return hints
