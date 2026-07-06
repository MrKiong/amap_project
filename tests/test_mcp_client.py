from __future__ import annotations

import asyncio
import unittest

from config.settings import Settings
from core.mcp_client import MCPClient, extract_json_text_payload, mask_url_secret
from core.tool_schema import ToolSchema


class MCPClientTest(unittest.TestCase):
    def test_disabled_mode_returns_no_tools(self) -> None:
        async def run_case() -> list[dict]:
            settings = Settings(
                log_level="INFO",
                deepseek_api_key="",
                deepseek_base_url="",
                deepseek_model="deepseek-v4",
                amap_mcp_mode="disabled",
                amap_mcp_url="",
                amap_maps_api_key="",
                database_url="sqlite:///data/test.sqlite",
            )
            client = MCPClient(settings)
            return await client.list_tools()

        tools = asyncio.run(run_case())
        self.assertEqual(tools, [])

    def test_amap_key_is_added_to_streamable_http_url(self) -> None:
        settings = Settings(
            log_level="INFO",
            deepseek_api_key="",
            deepseek_base_url="",
            deepseek_model="deepseek-v4",
            amap_mcp_mode="streamable_http",
            amap_mcp_url="https://mcp.amap.com/mcp",
            amap_maps_api_key="test-key",
            database_url="sqlite:///data/test.sqlite",
        )

        self.assertEqual(settings.amap_mcp_endpoint, "https://mcp.amap.com/mcp?key=test-key")

    def test_decode_sse_json_rpc_response(self) -> None:
        settings = Settings(
            log_level="INFO",
            deepseek_api_key="",
            deepseek_base_url="",
            deepseek_model="deepseek-v4",
            amap_mcp_mode="disabled",
            amap_mcp_url="",
            amap_maps_api_key="",
            database_url="sqlite:///data/test.sqlite",
        )
        client = MCPClient(settings)
        raw = 'event: message\n' 'data: {"jsonrpc":"2.0","id":1,"result":{"tools":[]}}\n\n'

        decoded = client._decode_http_body(raw, "text/event-stream")

        self.assertEqual(decoded["result"]["tools"], [])

    def test_mask_url_secret_hides_amap_key(self) -> None:
        masked = mask_url_secret("https://mcp.amap.com/mcp?key=abcdef123456&x=1")

        self.assertEqual(masked, "https://mcp.amap.com/mcp?key=abcd...3456&x=1")
        self.assertNotIn("abcdef123456", masked)

    def test_extract_json_text_payload(self) -> None:
        payload = extract_json_text_payload(
            {"content": [{"type": "text", "text": '{"pois":[{"name":"测试餐厅"}]}'}]}
        )

        self.assertEqual(payload["pois"][0]["name"], "测试餐厅")

    def test_tool_schema_from_mcp_tool(self) -> None:
        schema = ToolSchema.from_mcp_tool(
            {
                "name": "maps_around_search",
                "description": "周边搜",
                "inputSchema": {
                    "type": "object",
                    "properties": {"keywords": {"type": "string"}},
                    "required": ["keywords"],
                },
            }
        )

        self.assertEqual(schema.name, "maps_around_search")
        self.assertEqual(schema.to_openai_tool()["function"]["parameters"]["required"], ["keywords"])

    def test_call_tool_uses_ttl_cache_for_cacheable_amap_tools(self) -> None:
        class CountingMCPClient(MCPClient):
            def __init__(self, settings: Settings):
                super().__init__(settings)
                self.calls = 0

            async def _call_real_tool(self, tool_name: str, arguments: dict) -> dict:
                self.calls += 1
                return {"content": {"calls": self.calls, "arguments": dict(arguments)}}

        async def run_case() -> tuple[int, dict]:
            settings = Settings(
                log_level="INFO",
                deepseek_api_key="",
                deepseek_base_url="",
                deepseek_model="deepseek-v4",
                amap_mcp_mode="streamable_http",
                amap_mcp_url="https://mcp.amap.com/mcp",
                amap_maps_api_key="test-key",
                database_url="sqlite:///data/test.sqlite",
            )
            client = CountingMCPClient(settings)
            first = await client.call_tool("maps_geo", {"city": "北京", "address": "国典华园"})
            first["content"]["mutated"] = True
            second = await client.call_tool("maps_geo", {"address": "国典华园", "city": "北京"})
            return client.calls, second

        calls, second = asyncio.run(run_case())

        self.assertEqual(calls, 1)
        self.assertEqual(second["content"]["calls"], 1)
        self.assertNotIn("mutated", second["content"])
