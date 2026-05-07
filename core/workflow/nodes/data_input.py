"""Data input node — static data, file content, or text input."""
from __future__ import annotations

import json
from typing import Any

from core.workflow.base_node import BaseNode
from core.workflow.registry import NodeRegistry


@NodeRegistry.register
class DataInputNode(BaseNode):
    name = "input"
    display_name = "데이터 입력"
    description = "정적 데이터, 텍스트, JSON 입력"
    category = "data"

    async def execute(
        self,
        input_data: list[dict[str, Any]],
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Return configured static data.

        Params:
            mode: "text" | "json" | "list" (default: "text")
            value: The data value (string for text, dict/list for json)
        """
        mode = params.get("mode", "text")
        value = params.get("value", "")

        if mode == "json":
            if isinstance(value, dict):
                return [value]
            elif isinstance(value, list):
                return [{"item": v} if not isinstance(v, dict) else v for v in value]
            else:
                try:
                    parsed = json.loads(str(value))
                    if isinstance(parsed, list):
                        return [
                            {"item": v} if not isinstance(v, dict) else v
                            for v in parsed
                        ]
                    return [parsed] if isinstance(parsed, dict) else [{"value": parsed}]
                except (json.JSONDecodeError, TypeError):
                    return [{"value": str(value)}]
        elif mode == "list":
            items = str(value).split("\n") if isinstance(value, str) else list(value)
            return [
                {"item": item.strip(), "index": i}
                for i, item in enumerate(items)
                if item.strip()
            ]
        else:
            # text mode
            return [{"text": str(value)}]

    def get_parameter_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["text", "json", "list"],
                    "default": "text",
                    "description": "입력 데이터 형식",
                },
                "value": {
                    "type": "string",
                    "default": "",
                    "description": "입력 데이터 값",
                },
            },
        }
