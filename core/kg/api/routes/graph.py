"""Graph exploration endpoints: subgraph, neighbors, search."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query

from kg.api.deps import get_async_neo4j_session
from kg.api.entity_groups import _LABEL_TO_GROUP, get_color_for_label, get_group_for_label
from kg.api.models import GraphResponse
from kg.api.serializers import serialize_neo4j_value

logger = logging.getLogger(__name__)

router = APIRouter(tags=["graph"])


# ---------------------------------------------------------------------------
# Helpers (ported from poc/kg_visualizer_api.py)
# ---------------------------------------------------------------------------


def _extract_node(record: Any, key: str) -> dict[str, Any] | None:
    """Extract a node from a record into a serializable dict."""
    node = record.get(key) if isinstance(record, dict) else None
    if node is None:
        return None

    if hasattr(node, "element_id") and hasattr(node, "labels"):
        props = {k: serialize_neo4j_value(v) for k, v in dict(node).items()}
        labels = list(node.labels)
        primary_label = labels[0] if labels else "Unknown"
        return {
            "id": node.element_id,
            "labels": labels,
            "primaryLabel": primary_label,
            "group": get_group_for_label(primary_label),
            "color": get_color_for_label(primary_label),
            "properties": props,
            "displayName": props.get("name", props.get("title", primary_label)),
        }
    return None


def _extract_relationship(record: Any, key: str) -> dict[str, Any] | None:
    """Extract a relationship from a record into a serializable dict."""
    rel = record.get(key) if isinstance(record, dict) else None
    if rel is None:
        return None

    if hasattr(rel, "type") and hasattr(rel, "start_node"):
        props = {k: serialize_neo4j_value(v) for k, v in dict(rel).items()}
        return {
            "id": rel.element_id,
            "type": rel.type,
            "sourceId": rel.start_node.element_id,
            "targetId": rel.end_node.element_id,
            "properties": props,
        }
    return None


def _collect_graph(records: list[Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Iterate over a list of records and collect unique nodes and edges."""
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}

    for record in records:
        n = _extract_node(record, "n")
        if n:
            nodes[n["id"]] = n

        m = _extract_node(record, "m")
        if m:
            nodes[m["id"]] = m

        r = _extract_relationship(record, "r")
        if r:
            edges[r["id"]] = r

    return nodes, edges


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/subgraph", response_model=GraphResponse)
async def subgraph(
    label: str = Query(default="Vessel", description="Node label to query"),  # noqa: B008
    limit: int = Query(  # noqa: B008
        default=50, ge=1, le=200, description="Maximum nodes to return"
    ),
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
) -> GraphResponse:
    """Fetch nodes of a given label with their relationships.

    Args:
        label: Neo4j node label (e.g. ``Vessel``, ``Port``).
        limit: Maximum number of center nodes (1--200).
    """
    if label not in _LABEL_TO_GROUP:
        return GraphResponse(
            nodes=[],
            edges=[],
            meta={"error": f"Unknown or disallowed label: {label}"},
        )

    cypher = f"""
    MATCH (n:{label})
    WITH n LIMIT $limit
    OPTIONAL MATCH (n)-[r]-(m)
    RETURN n, r, m
    """

    result = await session.run(cypher, {"limit": limit})
    records = [record async for record in result]
    nodes, edges = _collect_graph(records)

    return GraphResponse(
        nodes=list(nodes.values()),  # type: ignore[arg-type]
        edges=list(edges.values()),  # type: ignore[arg-type]
        meta={
            "label": label,
            "limit": limit,
            "nodeCount": len(nodes),
            "edgeCount": len(edges),
        },
    )


@router.get("/neighbors", response_model=GraphResponse)
async def neighbors(
    nodeId: str = Query(..., description="Element ID of the center node"),  # noqa: B008
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
) -> GraphResponse:
    """Expand neighbors of a specific node.

    Args:
        nodeId: The Neo4j element ID of the center node.
    """
    cypher = """
    MATCH (n)
    WHERE elementId(n) = $nodeId
    OPTIONAL MATCH (n)-[r]-(m)
    RETURN n, r, m
    """

    result = await session.run(cypher, {"nodeId": nodeId})
    records = [record async for record in result]
    nodes, edges = _collect_graph(records)

    return GraphResponse(
        nodes=list(nodes.values()),  # type: ignore[arg-type]
        edges=list(edges.values()),  # type: ignore[arg-type]
        meta={
            "centerNodeId": nodeId,
            "nodeCount": len(nodes),
            "edgeCount": len(edges),
        },
    )


@router.get("/search", response_model=GraphResponse)
async def search(
    q: str = Query(..., min_length=1, description="Search query string"),  # noqa: B008
    limit: int = Query(default=30, ge=1, le=100, description="Maximum results"),  # noqa: B008
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
) -> GraphResponse:
    """Search nodes by name, title, or description.

    Args:
        q: Search term (uses ``CONTAINS`` matching).
        limit: Maximum number of center nodes (1--100).
    """
    cypher = """
    MATCH (n)
    WHERE n.name CONTAINS $query
       OR n.title CONTAINS $query
       OR n.nameEn CONTAINS $query
       OR n.description CONTAINS $query
    WITH n LIMIT $limit
    OPTIONAL MATCH (n)-[r]-(m)
    RETURN n, r, m
    """

    result = await session.run(cypher, {"query": q, "limit": limit})
    records = [record async for record in result]
    nodes, edges = _collect_graph(records)

    return GraphResponse(
        nodes=list(nodes.values()),  # type: ignore[arg-type]
        edges=list(edges.values()),  # type: ignore[arg-type]
        meta={
            "query": q,
            "nodeCount": len(nodes),
            "edgeCount": len(edges),
        },
    )
