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
from storage.repositories import PreferenceRecord
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


def build_memory() -> FoodMemory:
    settings = get_settings()
    configure_logging(settings.log_level)
    return FoodMemory(settings.database_path)


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


def add_preference_command(args: argparse.Namespace) -> None:
    memory = build_memory()
    record = PreferenceRecord(
        category=args.category,
        preference=args.preference,
        sentiment=args.sentiment,
        weight=args.weight,
        source_note=args.source_note or "",
    )
    preference_id = memory.add_preference(record)
    print(f"已添加饮食偏好 #{preference_id}: [{record.category}/{record.sentiment}] {record.preference}")


def list_preferences_command(args: argparse.Namespace) -> None:
    memory = build_memory()
    preferences = memory.list_preferences(limit=args.limit)
    if not preferences:
        print("暂无饮食偏好。")
        return
    for item in preferences:
        print(
            f"#{item['id']} [{item.get('category')}/{item.get('sentiment')}] "
            f"weight={item.get('weight')} | {item.get('preference')}"
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

    add_preference = subparsers.add_parser("add-preference", help="添加一条长期饮食偏好")
    add_preference.add_argument("--category", required=True, help="例如 cuisine/taste/scenario/budget/avoidance")
    add_preference.add_argument("--preference", required=True, help="偏好内容，例如 不喜欢排队超过15分钟")
    add_preference.add_argument(
        "--sentiment",
        default="like",
        choices=["like", "avoid", "neutral", "rule"],
        help="偏好倾向",
    )
    add_preference.add_argument("--weight", type=int, default=1, help="权重，越高越重要")
    add_preference.add_argument("--source-note", help="可选来源说明")
    add_preference.set_defaults(func=add_preference_command)

    list_preferences = subparsers.add_parser("list-preferences", help="查看已沉淀的饮食偏好")
    list_preferences.add_argument("--limit", type=int, default=20)
    list_preferences.set_defaults(func=list_preferences_command)

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
