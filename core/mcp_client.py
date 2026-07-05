from __future__ import annotations

import asyncio
import json
import itertools
import logging
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from config.settings import Settings


logger = logging.getLogger(__name__)


class MCPClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._request_ids = itertools.count(1)
        self._initialized = False
        self._http_session_id: str | None = None
        self._tools_cache: list[dict[str, Any]] | None = None
        logger.info(
            "MCP client initialized: mode=%s endpoint=%s",
            self.settings.amap_mcp_mode,
            mask_url_secret(self.settings.amap_mcp_endpoint),
        )
        if self.settings.amap_mcp_mode.lower() == "disabled":
            logger.info(
                "MCP real Amap lookup is disabled: no MCP tools will be exposed. "
                "Set AMAP_MCP_MODE=streamable_http to call Amap MCP."
            )
            if self.settings.amap_maps_api_key:
                logger.info(
                    "AMAP_MAPS_API_KEY is present but ignored because AMAP_MCP_MODE=disabled."
                )

    async def list_tools(self) -> list[dict[str, Any]]:
        if self.settings.amap_mcp_mode == "disabled":
            logger.info("MCP list_tools skipped: mode=disabled")
            return []
        if self._tools_cache is not None:
            return self._tools_cache
        logger.info("MCP list_tools start")
        response = await self._request("tools/list", {})
        tools = response.get("tools", []) if isinstance(response, dict) else []
        tool_names = [tool.get("name", "<unnamed>") for tool in tools if isinstance(tool, dict)]
        logger.info("MCP list_tools done: count=%s tools=%s", len(tool_names), tool_names)
        self._tools_cache = tools if isinstance(tools, list) else []
        return self._tools_cache

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if self.settings.amap_mcp_mode == "disabled":
            logger.info(
                "MCP call_tool skipped: mode=disabled tool=%s args=%s",
                tool_name,
                arguments,
            )
            return {"content": {"error": "MCP is disabled"}, "isError": True}
        return await self._call_real_tool(tool_name, arguments)

    async def _call_real_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        logger.info("MCP call_tool start: tool=%s args=%s", tool_name, arguments)
        result = await self._request(
            "tools/call",
            {"name": tool_name, "arguments": arguments},
        )
        logger.info("MCP call_tool done: tool=%s result=%s", tool_name, summarize_result(result))
        return result

    async def close(self) -> None:
        logger.info("MCP client closed: had_session=%s", bool(self._http_session_id))
        self._initialized = False
        self._http_session_id = None
        self._tools_cache = None

    async def _request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        mode = self.settings.amap_mcp_mode.lower()
        if mode in {"http", "streamable_http", "streamable-http"}:
            return await self._http_request(method, params)
        raise ValueError(f"Unsupported AMAP_MCP_MODE: {self.settings.amap_mcp_mode}")

    async def _http_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.settings.amap_mcp_endpoint:
            raise ValueError("AMAP_MCP_URL is required when AMAP_MCP_MODE=streamable_http")
        if not self._initialized:
            await self._initialize_http()
        payload = {
            "jsonrpc": "2.0",
            "id": next(self._request_ids),
            "method": method,
            "params": params,
        }
        logger.info("MCP HTTP request: method=%s id=%s", method, payload["id"])
        return await asyncio.to_thread(self._post_json_rpc, payload)

    async def _initialize_http(self) -> None:
        logger.info("MCP HTTP initialize start")
        payload = {
            "jsonrpc": "2.0",
            "id": next(self._request_ids),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "amap_project", "version": "0.1.0"},
            },
        }
        await asyncio.to_thread(self._post_json_rpc, payload)
        logger.info("MCP HTTP initialize accepted: session=%s", mask_secret(self._http_session_id))
        initialized_payload = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        }
        await asyncio.to_thread(self._post_json_rpc, initialized_payload)
        self._initialized = True
        logger.info("MCP HTTP initialized notification sent")

    def _post_json_rpc(self, payload: dict[str, Any]) -> dict[str, Any]:
        method = payload.get("method", "<unknown>")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._http_session_id:
            headers["Mcp-Session-Id"] = self._http_session_id

        request = urllib.request.Request(
            self.settings.amap_mcp_endpoint,
            method="POST",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
        )
        try:
            logger.info(
                "MCP HTTP POST start: method=%s endpoint=%s has_session=%s",
                method,
                mask_url_secret(self.settings.amap_mcp_endpoint),
                bool(self._http_session_id),
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                session_id = response.headers.get("Mcp-Session-Id")
                if session_id:
                    self._http_session_id = session_id
                status = getattr(response, "status", 200)
                content_type = response.headers.get("Content-Type", "")
                body = response.read().decode("utf-8")
                logger.info(
                    "MCP HTTP POST done: method=%s status=%s content_type=%s bytes=%s session=%s",
                    method,
                    status,
                    content_type,
                    len(body.encode("utf-8")),
                    mask_secret(self._http_session_id),
                )
                if status == 202 or not body.strip():
                    return {}
                raw = self._decode_http_body(body, content_type)
        except urllib.error.URLError as exc:
            logger.info("MCP HTTP POST failed: method=%s reason=%s", method, exc.reason)
            raise RuntimeError(f"MCP HTTP request failed: {exc.reason}") from exc
        if raw.get("error"):
            logger.info("MCP HTTP error response: method=%s error=%s", method, raw["error"])
            raise RuntimeError(f"MCP error: {raw['error']}")
        logger.info("MCP HTTP result: method=%s result=%s", method, summarize_result(raw.get("result", {})))
        return raw.get("result", {})

    def _decode_http_body(self, body: str, content_type: str) -> dict[str, Any]:
        if "text/event-stream" not in content_type:
            logger.info("MCP HTTP decode: format=json")
            return json.loads(body)

        logger.info("MCP HTTP decode: format=sse")
        event_data: list[str] = []
        for line in body.splitlines():
            if line.startswith("data:"):
                event_data.append(line.removeprefix("data:").strip())
        if not event_data:
            return {}
        return json.loads("\n".join(event_data))

def mask_secret(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"


def mask_url_secret(url: str) -> str:
    if not url:
        return ""
    parts = urlsplit(url)
    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key.lower() in {"key", "api_key", "apikey", "token", "access_token"}:
            query.append((key, mask_secret(value)))
        else:
            query.append((key, value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def extract_json_text_payload(result: dict[str, Any]) -> dict[str, Any]:
    content = result.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                try:
                    payload = json.loads(item["text"])
                except json.JSONDecodeError:
                    continue
                return payload if isinstance(payload, dict) else {}
    if isinstance(content, dict):
        return content
    return {}


def summarize_result(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        summary: dict[str, Any] = {"keys": sorted(result.keys())[:20]}
        for key in ("tools", "restaurants", "pois", "items", "results", "content"):
            value = result.get(key)
            if isinstance(value, list):
                summary[f"{key}_count"] = len(value)
            elif isinstance(value, dict):
                summary[f"{key}_keys"] = sorted(value.keys())[:20]
        payload = extract_json_text_payload(result)
        if payload:
            summary["payload_keys"] = sorted(payload.keys())[:20]
            for key in ("pois", "restaurants", "items", "results"):
                value = payload.get(key)
                if isinstance(value, list):
                    summary[f"payload_{key}_count"] = len(value)
                    names = [item.get("name") for item in value if isinstance(item, dict) and item.get("name")]
                    if names:
                        summary[f"payload_{key}_names"] = names[:5]
            if isinstance(payload.get("poi"), dict):
                poi = payload["poi"]
                summary["payload_poi_name"] = poi.get("name")
                summary["payload_poi_id"] = poi.get("id")
            for key in ("name", "id", "address"):
                if key in payload:
                    summary[f"payload_{key}"] = payload[key]
        return summary
    if isinstance(result, list):
        return {"type": "list", "count": len(result)}
    return {"type": type(result).__name__}
