from __future__ import annotations

import copy
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

    def to_openai_tool(self, strict: bool = False) -> dict[str, Any]:
        parameters = normalize_object_schema(self.input_schema)
        if strict:
            parameters = to_strict_json_schema(parameters)
        function: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "parameters": parameters,
        }
        if strict:
            function["strict"] = True
        return {
            "type": "function",
            "function": function,
        }


def normalize_object_schema(schema: dict[str, Any] | None) -> dict[str, Any]:
    normalized = copy.deepcopy(schema or {})
    if not normalized:
        normalized = {"type": "object", "properties": {}}
    normalized.setdefault("type", "object")
    normalized.setdefault("properties", {})
    return normalized


def to_strict_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    strict_schema = copy.deepcopy(schema)
    return _stricten_schema(strict_schema, make_optional_nullable=False)


def _stricten_schema(schema: dict[str, Any], make_optional_nullable: bool) -> dict[str, Any]:
    schema_type = schema.get("type")
    if schema_type is None and schema.get("properties") is not None:
        schema_type = "object"
        schema["type"] = "object"
    if make_optional_nullable:
        schema["type"] = _nullable_type(schema_type)

    if schema_type == "object" or schema.get("properties") is not None:
        properties = schema.setdefault("properties", {})
        original_required = set(schema.get("required") or [])
        schema["required"] = list(properties.keys())
        schema["additionalProperties"] = False
        for name, child in properties.items():
            if isinstance(child, dict):
                _stricten_schema(child, make_optional_nullable=name not in original_required)
    elif schema_type == "array" and isinstance(schema.get("items"), dict):
        _stricten_schema(schema["items"], make_optional_nullable=False)
    return schema


def _nullable_type(schema_type: Any) -> Any:
    if isinstance(schema_type, list):
        return schema_type if "null" in schema_type else [*schema_type, "null"]
    if isinstance(schema_type, str):
        return [schema_type, "null"] if schema_type != "null" else schema_type
    return ["string", "null"]
