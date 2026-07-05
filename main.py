from __future__ import annotations

import argparse
import asyncio
import re
from typing import Any

from agents.food_agent.agent import FoodAgent
from agents.food_agent.memory import FoodMemory
from config.logging_config import configure_logging
from config.settings import get_settings
from core.agent_loop import AgentLoop
from core.llm_client import LLMClient
from core.mcp_client import MCPClient, extract_json_text_payload, mask_url_secret
from storage.repositories import MealRecord
from web_app import AgentWebServer


def build_runtime() -> tuple[FoodMemory, AgentLoop, MCPClient]:
    settings = get_settings()
    configure_logging(settings.log_level)
    memory = FoodMemory(settings.database_path)
    mcp_client = MCPClient(settings)
    llm_client = LLMClient(settings)
    agent = FoodAgent(memory)
    loop = AgentLoop(agent=agent, llm_client=llm_client, mcp_client=mcp_client)
    return memory, loop, mcp_client


async def chat_command(_args: argparse.Namespace) -> None:
    _memory, agent_loop, mcp_client = build_runtime()
    print("个人餐饮推荐 Agent 已启动。输入 exit / quit 结束。")
    try:
        while True:
            user_input = input("\n你：").strip()
            if not user_input:
                continue
            if user_input.lower() in {"exit", "quit", "q"}:
                break
            answer = await agent_loop.run(user_input)
            print(f"\nAgent：{answer}")
    finally:
        await mcp_client.close()


def add_meal_command(args: argparse.Namespace) -> None:
    memory, _agent_loop, _mcp_client = build_runtime()
    record = MealRecord(
        restaurant_name=args.restaurant_name,
        location=args.location or "",
        cuisine=args.cuisine or "",
        avg_price=args.avg_price,
        rating=args.rating,
        dishes=args.dishes or "",
        scenario=args.scenario or "",
        companions=args.companions or "",
        comment=args.comment or "",
        pros=args.pros or "",
        cons=args.cons or "",
        revisit_willingness=args.revisit_willingness or "",
    )
    meal_id = memory.add_meal(record)
    print(f"已添加用餐记录 #{meal_id}: {record.restaurant_name}")


def list_meals_command(args: argparse.Namespace) -> None:
    memory, _agent_loop, _mcp_client = build_runtime()
    meals = memory.recent_meals(limit=args.limit)
    if not meals:
        print("暂无用餐记录。")
        return
    for meal in meals:
        rating = meal.get("rating")
        price = meal.get("avg_price")
        print(
            f"#{meal['id']} {meal['restaurant_name']} | {meal.get('cuisine') or '未标注'} | "
            f"评分 {rating if rating is not None else '-'} | 人均 {price if price is not None else '-'} | "
            f"{meal.get('comment') or ''}"
        )


async def search_nearby_command(args: argparse.Namespace) -> None:
    _memory, _agent_loop, mcp_client = build_runtime()
    try:
        location = args.location
        if not is_lng_lat(location):
            geo_result = await mcp_client.call_tool(
                "maps_geo",
                {"address": args.location, "city": args.city},
            )
            geo_payload = extract_json_text_payload(geo_result)
            geo_results = geo_payload.get("results", [])
            if not isinstance(geo_results, list) or not geo_results:
                raise RuntimeError(f"maps_geo 没有找到地址：{args.location}")
            location = str(geo_results[0]["location"])

        result = await mcp_client.call_tool(
            "maps_around_search",
            {"location": location, "keywords": args.keywords, "radius": str(args.radius)},
        )
        print_tool_result(result)
    finally:
        await mcp_client.close()


def web_command(args: argparse.Namespace) -> None:
    _memory, agent_loop, mcp_client = build_runtime()
    AgentWebServer(agent_loop=agent_loop, mcp_client=mcp_client).serve(args.host, args.port)


def doctor_command(_args: argparse.Namespace) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    print("配置检查")
    print(f"- LOG_LEVEL: {settings.log_level}")
    print(f"- LLM: {'已配置' if settings.llm_configured else '未配置，将使用本地降级回复'}")
    print(f"- DEEPSEEK_MODEL: {settings.deepseek_model}")
    print(f"- MCP mode: {settings.amap_mcp_mode}")
    print(f"- MCP endpoint: {mask_url_secret(settings.amap_mcp_endpoint) or '-'}")
    print(f"- AMAP_MAPS_API_KEY: {'已填写' if settings.amap_maps_api_key else '未填写'}")
    print(f"- DATABASE: {settings.database_path}")
    if settings.amap_mcp_mode == "disabled":
        print("提示：当前不会调用高德 MCP，也不会向 LLM 暴露 MCP 工具。")
    elif settings.amap_mcp_mode not in {"http", "streamable_http", "streamable-http"}:
        print("提示：MCP mode 不受支持，请使用 streamable_http。")


def print_tool_result(result: dict[str, Any]) -> None:
    content = result.get("content", result)
    payload = extract_json_text_payload(result)
    if isinstance(payload.get("pois"), list):
        print("来源：amap_mcp")
        for item in payload["pois"]:
            print(
                f"- {item.get('name', '未知餐厅')} | "
                f"{item.get('type', item.get('typecode', '未知类型'))} | "
                f"{item.get('address', '')}"
            )
        return
    if isinstance(content, dict) and isinstance(content.get("restaurants"), list):
        print(f"来源：{content.get('source', 'mcp')}")
        for item in content["restaurants"]:
            print(
                f"- {item.get('name', '未知餐厅')} | {item.get('cuisine', '未知菜系')} | "
                f"人均 {item.get('avg_price', '-')} | {item.get('address', '')}"
            )
        return
    print(content)


def is_lng_lat(value: str) -> bool:
    return bool(re.fullmatch(r"\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?\s*", value))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="个人餐饮推荐 Agent CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    chat = subparsers.add_parser("chat", help="进入多轮餐饮推荐对话")
    chat.set_defaults(func=lambda args: asyncio.run(chat_command(args)))

    add_meal = subparsers.add_parser("add-meal", help="添加一条历史用餐记录")
    add_meal.add_argument("--restaurant-name", required=True)
    add_meal.add_argument("--location")
    add_meal.add_argument("--cuisine")
    add_meal.add_argument("--avg-price", type=float)
    add_meal.add_argument("--rating", type=float)
    add_meal.add_argument("--dishes")
    add_meal.add_argument("--scenario")
    add_meal.add_argument("--companions")
    add_meal.add_argument("--comment")
    add_meal.add_argument("--pros")
    add_meal.add_argument("--cons")
    add_meal.add_argument("--revisit-willingness")
    add_meal.set_defaults(func=add_meal_command)

    list_meals = subparsers.add_parser("list-meals", help="查看最近的用餐记录")
    list_meals.add_argument("--limit", type=int, default=20)
    list_meals.set_defaults(func=list_meals_command)

    search = subparsers.add_parser("search-nearby", help="通过 MCP 搜索附近餐厅")
    search.add_argument("--location", required=True)
    search.add_argument("--city", default="北京")
    search.add_argument("--keywords", default="餐厅")
    search.add_argument("--radius", type=int, default=1200)
    search.set_defaults(func=lambda args: asyncio.run(search_nearby_command(args)))

    web = subparsers.add_parser("web", help="启动本地 Web 测试页面")
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8765)
    web.set_defaults(func=web_command)

    doctor = subparsers.add_parser("doctor", help="检查当前 LLM/MCP 配置")
    doctor.set_defaults(func=doctor_command)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
