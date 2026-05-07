"""Data transform node — JSONPath extraction, filtering, mapping."""
from __future__ import annotations

import logging
from typing import Any

from core.workflow.base_node import BaseNode
from core.workflow.registry import NodeRegistry

logger = logging.getLogger(__name__)


@NodeRegistry.register
class TransformNode(BaseNode):
    name = "process"
    display_name = "데이터 변환"
    description = "JSONPath 추출, 필터, 매핑, 텍스트 가공"
    category = "data"

    # Whitelisted operations (Phase 1 — no arbitrary code execution)
    OPERATIONS = {
        "extract_field",
        "rename_fields",
        "filter_by_value",
        "template",
        "split_text",
        "merge",
        "select_fields",
    }

    async def execute(
        self,
        input_data: list[dict[str, Any]],
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Transform input data.

        Params:
            operation: Transform operation name (required)
            config: Operation-specific configuration dict
        """
        operation = params.get("operation", "extract_field")
        config = params.get("config", {})

        if operation not in self.OPERATIONS:
            raise ValueError(
                f"Unknown operation '{operation}'. "
                f"Available: {sorted(self.OPERATIONS)}"
            )

        handler = getattr(self, f"_op_{operation}", None)
        if handler is None:
            raise ValueError(f"Operation '{operation}' not implemented")

        return handler(input_data, config)

    def _op_extract_field(
        self, data: list[dict[str, Any]], config: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Extract a nested field using dot-notation path."""
        field_path = config.get("field", "")
        output_key = config.get("output_key", "value")
        results = []
        for item in data:
            value = self._resolve_path(item, field_path)
            results.append({output_key: value})
        return results

    def _op_rename_fields(
        self, data: list[dict[str, Any]], config: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Rename fields: {"old_name": "new_name"}."""
        mapping = config.get("mapping", {})
        results = []
        for item in data:
            new_item = {}
            for k, v in item.items():
                new_key = mapping.get(k, k)
                new_item[new_key] = v
            results.append(new_item)
        return results

    def _op_filter_by_value(
        self, data: list[dict[str, Any]], config: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Filter items where field matches value."""
        field = config.get("field", "")
        value = config.get("value")
        op = config.get("operator", "eq")

        results = []
        for item in data:
            item_val = self._resolve_path(item, field)
            if op == "eq" and item_val == value:
                results.append(item)
            elif op == "neq" and item_val != value:
                results.append(item)
            elif (
                op == "contains"
                and value is not None
                and str(value) in str(item_val)
            ):
                results.append(item)
            elif (
                op == "gt"
                and item_val is not None
                and value is not None
                and item_val > value
            ):
                results.append(item)
            elif (
                op == "lt"
                and item_val is not None
                and value is not None
                and item_val < value
            ):
                results.append(item)
        return results

    def _op_template(
        self, data: list[dict[str, Any]], config: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Apply string template with {{field}} substitution."""
        template = config.get("template", "")
        output_key = config.get("output_key", "text")
        results = []
        for item in data:
            text = template
            for key, val in item.items():
                text = text.replace(f"{{{{{key}}}}}", str(val))
            results.append({output_key: text, **item})
        return results

    def _op_split_text(
        self, data: list[dict[str, Any]], config: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Split a text field into multiple items."""
        field = config.get("field", "text")
        delimiter = config.get("delimiter", "\n")
        results = []
        for item in data:
            text = str(self._resolve_path(item, field) or "")
            parts = text.split(delimiter)
            for i, part in enumerate(parts):
                if part.strip():
                    results.append({
                        "text": part.strip(),
                        "index": i,
                        **{k: v for k, v in item.items() if k != field},
                    })
        return results

    def _op_merge(
        self, data: list[dict[str, Any]], config: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Merge all input items into a single item."""
        if not data:
            return []
        merged: dict[str, Any] = {}
        for item in data:
            merged.update(item)
        return [merged]

    def _op_select_fields(
        self, data: list[dict[str, Any]], config: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Select only specified fields."""
        fields = config.get("fields", [])
        if not fields:
            return data
        return [{k: item.get(k) for k in fields if k in item} for item in data]

    @staticmethod
    def _resolve_path(obj: dict[str, Any], path: str) -> Any:
        """Resolve dot-notation path: 'a.b.c' -> obj['a']['b']['c']."""
        if not path:
            return obj
        current: Any = obj
        for part in path.split("."):
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, (list, tuple)) and part.isdigit():
                idx = int(part)
                current = current[idx] if idx < len(current) else None
            else:
                return None
        return current

    def get_parameter_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["operation"],
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": sorted(self.OPERATIONS),
                    "description": "변환 작업",
                },
                "config": {
                    "type": "object",
                    "description": "작업별 설정",
                },
            },
        }
