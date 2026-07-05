from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolSchema:
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mcp_tool(cls, tool: dict[str, Any]) -> "ToolSchema":
        name = tool.get("name")
        if not name:
            raise ValueError(f"MCP tool is missing name: {tool}")
        return cls(
            name=str(name),
            description=str(tool.get("description") or ""),
            input_schema=tool.get("inputSchema") or tool.get("input_schema") or {},
        )

    def to_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema or {"type": "object", "properties": {}},
            },
        }
