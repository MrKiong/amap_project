from __future__ import annotations

import json
import logging
import re
from typing import Any

from agents.base_agent import BaseAgent
from agents.food_agent.context import USER_PROFILE
from agents.food_agent.memory import FoodMemory
from agents.food_agent.prompts import FOOD_SYSTEM_PROMPT
from core.mcp_client import extract_json_text_payload
from core.tool_schema import ToolSchema


logger = logging.getLogger(__name__)


class FoodAgent(BaseAgent):
    name = "food_agent"

    def __init__(self, memory: FoodMemory):
        self.memory = memory

    async def build_system_prompt(self) -> str:
        profile = json.dumps(USER_PROFILE, ensure_ascii=False, indent=2)
        return f"{FOOD_SYSTEM_PROMPT}\n\n用户静态资料：\n{profile}"

    async def build_context(self, user_input: str) -> dict[str, Any]:
        return {
            "user_profile": USER_PROFILE,
            "preference_summary": self.memory.preference_summary(),
            "recent_meals": self.memory.recent_meals(limit=8),
            "pitfalls": self.memory.pitfalls(limit=5),
            "parsed_request": self.parse_request(user_input),
        }

    async def get_available_tools(self) -> list[ToolSchema]:
        return []

    async def build_external_context(
        self,
        user_input: str,
        context: dict[str, Any],
        mcp_client: Any,
    ) -> dict[str, Any]:
        parsed = context.get("parsed_request", {})
        tools = await mcp_client.list_tools()
        tool_names = {tool.get("name") for tool in tools if isinstance(tool, dict)}
        required = {"maps_geo", "maps_around_search"}
        if not required.issubset(tool_names):
            logger.info("FoodAgent restaurant search skipped: missing_mcp_tools=%s", sorted(required - tool_names))
            return {
                "restaurant_search": {
                    "status": "skipped",
                    "reason": "高德 MCP 未启用或缺少 maps_geo/maps_around_search",
                    "candidates": [],
                }
            }

        try:
            search_context = await self._search_restaurant_candidates(user_input, parsed, mcp_client)
        except Exception as exc:
            logger.info("FoodAgent restaurant search failed: %s", exc)
            search_context = {
                "status": "error",
                "error": str(exc),
                "candidates": [],
            }
        return {"restaurant_search": search_context}

    def parse_request(self, user_input: str) -> dict[str, Any]:
        budget_range = self._parse_budget_range(user_input)
        budget_match = re.search(r"(\d{2,4})\s*(?:元|块|左右)?", user_input)
        location = ""
        if any(word in user_input for word in ("家附近", "家周边", "家门口", "家里附近")):
            location = USER_PROFILE["home_area"]
        else:
            for marker in ("附近", "周边"):
                if marker in user_input:
                    before = user_input.split(marker)[0].strip()
                    if before.endswith("家"):
                        location = USER_PROFILE["home_area"]
                    else:
                        chunks = re.split(r"[，,。！？\s]", before)
                        location = chunks[-1].strip("我在去到离") if chunks else ""
                    break

        return {
            "location": location or USER_PROFILE["home_area"],
            "city": USER_PROFILE["default_city"],
            "budget": int(budget_match.group(1)) if budget_match else None,
            "budget_range": budget_range,
            "people_count": self._parse_people_count(user_input),
            "is_solo": "一个人" in user_input or "自己" in user_input,
            "avoid_spicy": any(word in user_input for word in ("不辣", "不想吃辣", "不要辣", "太辣")),
            "meal_time": self._parse_meal_time(user_input),
            "travel_mode": "电动车/骑行" if any(word in user_input for word in ("电动车", "骑车", "骑行")) else "",
        }

    async def fallback_response(
        self,
        user_input: str,
        context: dict[str, Any],
        tool_results: list[dict[str, Any]] | None = None,
    ) -> str:
        parsed = context.get("parsed_request", {})
        budget = self._format_budget(parsed)
        location = parsed.get("location") or USER_PROFILE["home_area"]
        preference_summary = context.get("preference_summary", "暂无历史用餐记录。")
        candidates = self._extract_candidates_from_context(context) or self._extract_candidates(tool_results or [])

        if candidates:
            top = candidates[0]
            backup = candidates[1] if len(candidates) > 1 else None
            top_name = top.get("name", "附近一家清淡小馆")
            top_address = top.get("address") or top.get("location") or location
            backup_text = (
                f"备选：{backup.get('name')}，如果首推排队或你想换口味，可以考虑它。"
                if backup
                else "备选：选择同商圈里评分稳定、排队较短的粤菜或面食小店。"
            )
        else:
            top_name = "国典华园附近的清淡粤菜/面食小馆"
            top_address = location
            backup_text = "备选：日式定食或韩式简餐，通常一个人吃更省心，辣度也更可控。"

        spicy_note = "你这次明确不想吃太辣，所以我会避开川湘菜、重口火锅和香锅。" if parsed.get("avoid_spicy") else "如果想控制口味风险，优先选辣度可调的店。"
        solo_note = "一个人吃的话，优先选出餐稳定、不需要凑桌、翻台快的店。" if parsed.get("is_solo") else "如果同行人数变化，可以再按座位和排队情况微调。"

        return (
            f"【fallback_response】首推：{top_name}\n"
            f"理由：地点按「{location}」处理，预算按 {budget} 控制；{spicy_note}{solo_note}\n"
            f"结合你的历史偏好：{preference_summary}\n"
            "适合点：清淡主菜 + 一份主食，或定食/套餐，避免重辣招牌菜。\n"
            f"预计预算：{budget}，建议留 10-20 元浮动。\n"
            f"距离/交通：优先步行可达；当前地址线索为 {top_address}。\n"
            f"{backup_text}\n"
            "不推荐：这次不优先推重辣川湘菜、排队型网红店和必须多人分享的大份菜，因为和你的场景不匹配。"
        )

    async def _search_restaurant_candidates(
        self,
        user_input: str,
        parsed: dict[str, Any],
        mcp_client: Any,
    ) -> dict[str, Any]:
        location_text = str(parsed.get("location") or USER_PROFILE["home_area"])
        city = str(parsed.get("city") or USER_PROFILE["default_city"])
        radius = self._search_radius(user_input, parsed)
        center = await self._geocode_location(mcp_client, location_text, city)
        candidates = await self._search_around(mcp_client, center, radius, self._search_keywords(user_input, parsed))
        candidates = self._dedupe_candidates(candidates)[:10]
        detailed = await self._attach_details(mcp_client, candidates[:8])
        logger.info(
            "FoodAgent restaurant search done: location=%s center=%s radius=%s candidates=%s names=%s",
            location_text,
            center,
            radius,
            len(detailed),
            [item.get("name") for item in detailed[:5]],
        )
        return {
            "status": "ok",
            "location_text": location_text,
            "center": center,
            "city": city,
            "radius": radius,
            "keywords": self._search_keywords(user_input, parsed),
            "candidates": detailed,
        }

    async def _geocode_location(self, mcp_client: Any, location_text: str, city: str) -> str:
        result = await mcp_client.call_tool("maps_geo", {"address": location_text, "city": city})
        payload = extract_json_text_payload(result)
        results = payload.get("results", [])
        if not isinstance(results, list) or not results:
            raise RuntimeError(f"maps_geo 没有找到位置：{location_text}")
        center = results[0].get("location")
        if not center:
            raise RuntimeError(f"maps_geo 返回缺少 location：{location_text}")
        return str(center)

    async def _search_around(
        self,
        mcp_client: Any,
        center: str,
        radius: int,
        keywords: list[str],
    ) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for keyword in keywords:
            result = await mcp_client.call_tool(
                "maps_around_search",
                {"location": center, "keywords": keyword, "radius": str(radius)},
            )
            payload = extract_json_text_payload(result)
            pois = payload.get("pois", [])
            if isinstance(pois, list):
                candidates.extend(item for item in pois if isinstance(item, dict))
            if len(self._dedupe_candidates(candidates)) >= 10:
                break
        return candidates

    async def _attach_details(self, mcp_client: Any, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        detailed: list[dict[str, Any]] = []
        for item in candidates:
            enriched = self._compact_poi(item)
            poi_id = item.get("id")
            if poi_id:
                try:
                    detail = await mcp_client.call_tool("maps_search_detail", {"id": str(poi_id)})
                    detail_payload = extract_json_text_payload(detail)
                    enriched["detail"] = self._compact_detail(detail_payload)
                except Exception as exc:
                    enriched["detail_error"] = str(exc)
            detailed.append(enriched)
        return detailed

    def _compact_poi(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": item.get("id"),
            "name": item.get("name"),
            "address": item.get("address"),
            "type": item.get("type"),
            "typecode": item.get("typecode"),
            "location": item.get("location"),
        }

    def _compact_detail(self, payload: dict[str, Any]) -> dict[str, Any]:
        detail: dict[str, Any] = {}
        source = payload.get("poi") if isinstance(payload.get("poi"), dict) else payload
        if not isinstance(source, dict):
            return detail
        for key in ("id", "name", "address", "type", "typecode", "tel", "business_area", "tag", "rating", "cost"):
            if source.get(key):
                detail[key] = source[key]
        return detail

    def _dedupe_candidates(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for item in candidates:
            key = str(item.get("id") or f"{item.get('name')}|{item.get('address')}")
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique

    def _search_keywords(self, user_input: str, parsed: dict[str, Any]) -> list[str]:
        keywords = ["餐厅 美食"]
        if parsed.get("avoid_spicy"):
            keywords.extend(["粤菜", "日料", "韩式简餐", "面馆"])
        for word in ("粤菜", "日料", "韩餐", "韩式", "面馆", "简餐", "清淡", "火锅", "烤肉"):
            if word in user_input and word not in keywords:
                keywords.append(word)
        return keywords[:5]

    def _search_radius(self, user_input: str, parsed: dict[str, Any]) -> int:
        if parsed.get("travel_mode"):
            return 4000
        if any(word in user_input for word in ("附近", "周边", "走路", "步行")):
            return 1500
        return 2500

    def _parse_budget_range(self, user_input: str) -> dict[str, int] | None:
        match = re.search(r"(\d{2,4})\s*[-~到至]\s*(\d{2,4})", user_input)
        if not match:
            return None
        low, high = int(match.group(1)), int(match.group(2))
        return {"min": min(low, high), "max": max(low, high)}

    def _parse_people_count(self, user_input: str) -> int | None:
        if "一个人" in user_input or "自己" in user_input:
            return 1
        if "两个人" in user_input or "俩人" in user_input:
            return 2
        match = re.search(r"(\d+)\s*(?:个人|人)", user_input)
        return int(match.group(1)) if match else None

    def _parse_meal_time(self, user_input: str) -> str:
        if any(word in user_input for word in ("晚上", "晚餐", "今晚")):
            return "晚餐"
        if "中午" in user_input or "午" in user_input:
            return "午餐"
        return ""

    def _format_budget(self, parsed: dict[str, Any]) -> str:
        budget_range = parsed.get("budget_range")
        if isinstance(budget_range, dict):
            return f"人均 {budget_range.get('min')}-{budget_range.get('max')} 元"
        if parsed.get("budget"):
            return f"人均 {parsed['budget']} 元左右"
        return f"人均 {USER_PROFILE['common_budget_lunch']} 元"

    def _extract_candidates_from_context(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        search = context.get("external_context", {}).get("restaurant_search", {})
        candidates = search.get("candidates", [])
        return [item for item in candidates if isinstance(item, dict)]

    def _extract_candidates(self, tool_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        candidate_lists: list[list[dict[str, Any]]] = []
        for result in tool_results:
            payload = extract_json_text_payload(result)
            if isinstance(payload, dict):
                for key in ("pois", "restaurants", "items", "results"):
                    if isinstance(payload.get(key), list):
                        candidates = [item for item in payload[key] if isinstance(item, dict)]
                        if candidates:
                            candidate_lists.append(candidates)
            content = result.get("content", result)
            if isinstance(content, dict):
                for key in ("pois", "restaurants", "items", "results"):
                    if isinstance(content.get(key), list):
                        candidates = [item for item in content[key] if isinstance(item, dict)]
                        if candidates:
                            candidate_lists.append(candidates)
            if isinstance(content, list):
                candidates = [item for item in content if isinstance(item, dict)]
                if candidates:
                    candidate_lists.append(candidates)

        for candidates in candidate_lists:
            named = [item for item in candidates if item.get("name")]
            if named:
                return named
        if candidate_lists:
            return candidate_lists[0]
        return []
