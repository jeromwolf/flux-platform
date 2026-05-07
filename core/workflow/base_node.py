"""Abstract base node interface (n8n INodeType pattern)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseNode(ABC):
    """Base class for all workflow node types.

    Subclasses must define class-level attributes:
        name: Unique node type identifier (e.g. "http_request")
        display_name: Human-readable name for UI (e.g. "HTTP 요청")
        description: Short description
        category: Node category for grouping (e.g. "network", "data", "ai")
    """

    name: str = ""
    display_name: str = ""
    description: str = ""
    category: str = "general"

    @abstractmethod
    async def execute(
        self,
        input_data: list[dict[str, Any]],
        params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Execute the node logic.

        Args:
            input_data: List of data items from upstream nodes.
            params: Node-specific parameters configured by user.

        Returns:
            List of output data items to pass to downstream nodes.

        Raises:
            NodeExecutionError: If execution fails.
        """
        ...

    def get_parameter_schema(self) -> dict[str, Any]:
        """Return JSON Schema for node parameters (UI inspector rendering).

        Returns:
            JSON Schema dict describing configurable parameters.
        """
        return {}

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Validate node parameters before execution.

        Args:
            params: User-configured parameters.

        Returns:
            List of validation error messages (empty = valid).
        """
        return []
