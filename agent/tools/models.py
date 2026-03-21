"""Tool data models."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolDefinition:
    """Definition of a tool available to the agent."""
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    required_params: tuple[str, ...] = ()
    category: str = "general"
    is_dangerous: bool = False

    def validate_input(self, inputs: dict[str, Any]) -> list[str]:
        """Validate tool inputs against required parameters.

        Returns:
            List of validation error messages. Empty = valid.
        """
        errors: list[str] = []
        for param in self.required_params:
            if param not in inputs:
                errors.append(f"Missing required parameter: {param}")
        return errors


@dataclass(frozen=True)
class ToolResult:
    """Result of a tool execution."""
    tool_name: str
    output: str
    success: bool = True
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
