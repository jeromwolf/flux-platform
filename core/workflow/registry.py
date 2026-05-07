"""Node type registry — plugin-style dynamic loading."""
from __future__ import annotations

import logging
from typing import Any

from core.workflow.base_node import BaseNode

logger = logging.getLogger(__name__)


class NodeRegistry:
    """Singleton registry mapping node type names to their classes."""

    _registry: dict[str, type[BaseNode]] = {}

    @classmethod
    def register(cls, node_class: type[BaseNode]) -> type[BaseNode]:
        """Register a node class. Can be used as decorator.

        Args:
            node_class: BaseNode subclass to register.

        Returns:
            The same node_class (for decorator chaining).

        Raises:
            ValueError: If node_class.name is empty or already registered.
        """
        if not node_class.name:
            raise ValueError(f"Node class {node_class.__name__} has no 'name' attribute")
        if node_class.name in cls._registry:
            logger.warning(f"Overwriting existing node type: {node_class.name}")
        cls._registry[node_class.name] = node_class
        logger.debug(f"Registered node type: {node_class.name}")
        return node_class

    @classmethod
    def get(cls, node_type: str) -> BaseNode:
        """Instantiate a node by type name.

        Args:
            node_type: Registered node type identifier.

        Returns:
            New instance of the registered BaseNode subclass.

        Raises:
            KeyError: If node_type is not registered.
        """
        if node_type not in cls._registry:
            available = ", ".join(sorted(cls._registry.keys()))
            raise KeyError(f"Unknown node type '{node_type}'. Available: {available}")
        return cls._registry[node_type]()

    @classmethod
    def list_types(cls) -> list[dict[str, Any]]:
        """List all registered node types with metadata.

        Returns:
            List of dicts with name, display_name, description, category, parameter_schema.
        """
        result = []
        for name, node_cls in sorted(cls._registry.items()):
            instance = node_cls()
            result.append({
                "name": name,
                "display_name": node_cls.display_name,
                "description": node_cls.description,
                "category": node_cls.category,
                "parameter_schema": instance.get_parameter_schema(),
            })
        return result

    @classmethod
    def has(cls, node_type: str) -> bool:
        """Check if a node type is registered."""
        return node_type in cls._registry

    @classmethod
    def clear(cls) -> None:
        """Remove all registered nodes (testing only)."""
        cls._registry.clear()
