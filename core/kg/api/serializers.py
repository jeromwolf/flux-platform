"""Shared serialization utilities for Neo4j values."""

from __future__ import annotations

from typing import Any


def serialize_neo4j_value(val: Any) -> Any:
    """Serialize Neo4j values to JSON-compatible types.

    Handles primitive types, collections, and Neo4j-specific spatial and
    temporal types.

    Args:
        val: Any value returned from a Neo4j query result.

    Returns:
        A JSON-serializable Python value.
    """
    if val is None:
        return None
    if isinstance(val, (str, int, float, bool)):
        return val
    if isinstance(val, list):
        return [serialize_neo4j_value(v) for v in val]
    if isinstance(val, dict):
        return {k: serialize_neo4j_value(v) for k, v in val.items()}
    # neo4j spatial / temporal types
    if hasattr(val, "x") and hasattr(val, "y"):
        return {"lat": val.y, "lon": val.x}
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)
