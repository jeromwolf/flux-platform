"""Tool registry for agent runtime."""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from agent.tools.models import ToolDefinition, ToolResult

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for agent tools.

    Manages tool registration, lookup, and execution.

    Example::

        registry = ToolRegistry()
        registry.register(
            ToolDefinition(name="search", description="Search the KG"),
            handler=search_handler,
        )
        result = registry.execute("search", {"query": "vessels"})
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, Callable[..., Any]] = {}

    def register(
        self,
        definition: ToolDefinition,
        handler: Callable[..., Any],
    ) -> ToolRegistry:
        """Register a tool with its handler function.

        Args:
            definition: Tool metadata and parameter schema.
            handler: Callable that executes the tool.

        Returns:
            Self for chaining.
        """
        self._tools[definition.name] = definition
        self._handlers[definition.name] = handler
        logger.info("Registered tool: %s", definition.name)
        return self

    def get(self, name: str) -> ToolDefinition | None:
        """Look up a tool definition by name."""
        return self._tools.get(name)

    def execute(self, name: str, inputs: dict[str, Any] | None = None) -> ToolResult:
        """Execute a registered tool.

        Args:
            name: Tool name.
            inputs: Tool input parameters.

        Returns:
            ToolResult with output or error.
        """
        defn = self._tools.get(name)
        if defn is None:
            return ToolResult(
                tool_name=name,
                output="",
                success=False,
                error=f"Unknown tool: {name}",
            )

        inputs = inputs or {}
        errors = defn.validate_input(inputs)
        if errors:
            return ToolResult(
                tool_name=name,
                output="",
                success=False,
                error="; ".join(errors),
            )

        handler = self._handlers[name]
        import time
        start = time.monotonic()
        try:
            output = handler(**inputs)
            duration = (time.monotonic() - start) * 1000
            return ToolResult(
                tool_name=name,
                output=str(output),
                success=True,
                duration_ms=round(duration, 2),
            )
        except Exception as exc:
            duration = (time.monotonic() - start) * 1000
            logger.error("Tool '%s' failed: %s", name, exc)
            return ToolResult(
                tool_name=name,
                output="",
                success=False,
                error=str(exc),
                duration_ms=round(duration, 2),
            )

    @property
    def tool_names(self) -> list[str]:
        """Names of all registered tools."""
        return list(self._tools.keys())

    @property
    def tool_count(self) -> int:
        """Number of registered tools."""
        return len(self._tools)

    def list_tools(self) -> list[ToolDefinition]:
        """Return all registered tool definitions."""
        return list(self._tools.values())

    def clear(self) -> None:
        """Remove all registered tools."""
        self._tools.clear()
        self._handlers.clear()
