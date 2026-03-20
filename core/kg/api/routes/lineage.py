"""Lineage exploration endpoints.

Provides REST API routes for querying data lineage and provenance
information stored in the Maritime Knowledge Graph.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path

from kg.api.deps import get_async_neo4j_session
from kg.api.models import (
    LineageNodesResponse,
    LineageResponse,
    LineageTimelineResponse,
)
from kg.api.serializers import serialize_neo4j_value
from kg.lineage.queries import (
    GET_ANCESTORS,
    GET_DESCENDANTS,
    GET_FULL_LINEAGE,
    GET_LINEAGE_TIMELINE,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["lineage"])


@router.get("/api/lineage/{entity_type}/{entity_id}", response_model=LineageResponse)
async def get_full_lineage(
    entity_type: str = Path(..., description="Entity label (e.g. Vessel)"),  # noqa: B008
    entity_id: str = Path(..., description="Entity identifier (e.g. VES-001)"),  # noqa: B008
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
) -> LineageResponse:
    """Return the full lineage graph (ancestors + descendants) for an entity.

    Args:
        entity_type: Neo4j node label of the tracked entity.
        entity_id: The entity's identifier property value.
        session: Async Neo4j session injected via FastAPI dependency.

    Returns:
        LineageResponse with nodes, edges, and metadata.
    """
    try:
        result = await session.run(
            GET_FULL_LINEAGE,
            {"entityType": entity_type, "entityId": entity_id},
        )

        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

        records = [record async for record in result]
        for record in records:
            rec = dict(record) if not isinstance(record, dict) else record
            node_info: dict[str, Any] = {
                "nodeId": serialize_neo4j_value(rec.get("nodeId")),
                "entityType": serialize_neo4j_value(rec.get("entityType")),
                "entityId": serialize_neo4j_value(rec.get("entityId")),
                "createdAt": serialize_neo4j_value(rec.get("createdAt")),
            }
            nodes.append(node_info)

            raw_edges = rec.get("edges", [])
            if raw_edges:
                for edge in raw_edges:
                    edge_info = serialize_neo4j_value(edge)
                    if isinstance(edge_info, dict) and edge_info.get("edgeId"):
                        edges.append(edge_info)

        return LineageResponse(
            nodes=nodes,
            edges=edges,
            meta={
                "entityType": entity_type,
                "entityId": entity_id,
                "nodeCount": len(nodes),
                "edgeCount": len(edges),
            },
        )
    except Exception as exc:
        logger.exception("Failed to fetch full lineage for %s/%s", entity_type, entity_id)
        raise HTTPException(
            status_code=500,
            detail=f"Lineage query failed: {exc}",
        )


@router.get(
    "/api/lineage/{entity_type}/{entity_id}/ancestors",
    response_model=LineageNodesResponse,
)
async def get_ancestors(
    entity_type: str = Path(..., description="Entity label"),  # noqa: B008
    entity_id: str = Path(..., description="Entity identifier"),  # noqa: B008
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
) -> LineageNodesResponse:
    """Return ancestor lineage nodes for an entity.

    Args:
        entity_type: Neo4j node label of the tracked entity.
        entity_id: The entity's identifier property value.
        session: Async Neo4j session injected via FastAPI dependency.

    Returns:
        LineageNodesResponse with ancestor nodes and metadata.
    """
    try:
        result = await session.run(
            GET_ANCESTORS,
            {"entityType": entity_type, "entityId": entity_id},
        )

        nodes: list[dict[str, Any]] = []
        records = [record async for record in result]
        for record in records:
            rec = dict(record) if not isinstance(record, dict) else record
            nodes.append({
                "nodeId": serialize_neo4j_value(rec.get("nodeId")),
                "entityType": serialize_neo4j_value(rec.get("entityType")),
                "entityId": serialize_neo4j_value(rec.get("entityId")),
                "createdAt": serialize_neo4j_value(rec.get("createdAt")),
                "depth": serialize_neo4j_value(rec.get("depth")),
            })

        return LineageNodesResponse(
            nodes=nodes,
            meta={
                "entityType": entity_type,
                "entityId": entity_id,
                "direction": "ancestors",
                "count": len(nodes),
            },
        )
    except Exception as exc:
        logger.exception("Failed to fetch ancestors for %s/%s", entity_type, entity_id)
        raise HTTPException(
            status_code=500,
            detail=f"Ancestor query failed: {exc}",
        )


@router.get(
    "/api/lineage/{entity_type}/{entity_id}/descendants",
    response_model=LineageNodesResponse,
)
async def get_descendants(
    entity_type: str = Path(..., description="Entity label"),  # noqa: B008
    entity_id: str = Path(..., description="Entity identifier"),  # noqa: B008
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
) -> LineageNodesResponse:
    """Return descendant lineage nodes for an entity.

    Args:
        entity_type: Neo4j node label of the tracked entity.
        entity_id: The entity's identifier property value.
        session: Async Neo4j session injected via FastAPI dependency.

    Returns:
        LineageNodesResponse with descendant nodes and metadata.
    """
    try:
        result = await session.run(
            GET_DESCENDANTS,
            {"entityType": entity_type, "entityId": entity_id},
        )

        nodes: list[dict[str, Any]] = []
        records = [record async for record in result]
        for record in records:
            rec = dict(record) if not isinstance(record, dict) else record
            nodes.append({
                "nodeId": serialize_neo4j_value(rec.get("nodeId")),
                "entityType": serialize_neo4j_value(rec.get("entityType")),
                "entityId": serialize_neo4j_value(rec.get("entityId")),
                "createdAt": serialize_neo4j_value(rec.get("createdAt")),
                "depth": serialize_neo4j_value(rec.get("depth")),
            })

        return LineageNodesResponse(
            nodes=nodes,
            meta={
                "entityType": entity_type,
                "entityId": entity_id,
                "direction": "descendants",
                "count": len(nodes),
            },
        )
    except Exception as exc:
        logger.exception("Failed to fetch descendants for %s/%s", entity_type, entity_id)
        raise HTTPException(
            status_code=500,
            detail=f"Descendant query failed: {exc}",
        )


@router.get(
    "/api/lineage/{entity_type}/{entity_id}/timeline",
    response_model=LineageTimelineResponse,
)
async def get_lineage_timeline(
    entity_type: str = Path(..., description="Entity label"),  # noqa: B008
    entity_id: str = Path(..., description="Entity identifier"),  # noqa: B008
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
) -> LineageTimelineResponse:
    """Return lineage events for an entity ordered chronologically.

    Args:
        entity_type: Neo4j node label of the tracked entity.
        entity_id: The entity's identifier property value.
        session: Async Neo4j session injected via FastAPI dependency.

    Returns:
        LineageTimelineResponse with chronological events and metadata.
    """
    try:
        result = await session.run(
            GET_LINEAGE_TIMELINE,
            {"entityType": entity_type, "entityId": entity_id},
        )

        events: list[dict[str, Any]] = []
        records = [record async for record in result]
        for record in records:
            rec = dict(record) if not isinstance(record, dict) else record
            events.append({
                "edgeId": serialize_neo4j_value(rec.get("edgeId")),
                "eventType": serialize_neo4j_value(rec.get("eventType")),
                "agent": serialize_neo4j_value(rec.get("agent")),
                "activity": serialize_neo4j_value(rec.get("activity")),
                "timestamp": serialize_neo4j_value(rec.get("timestamp")),
                "relatedEntityId": serialize_neo4j_value(rec.get("relatedEntityId")),
                "relatedEntityType": serialize_neo4j_value(rec.get("relatedEntityType")),
            })

        return LineageTimelineResponse(
            events=events,
            meta={
                "entityType": entity_type,
                "entityId": entity_id,
                "eventCount": len(events),
            },
        )
    except Exception as exc:
        logger.exception("Failed to fetch timeline for %s/%s", entity_type, entity_id)
        raise HTTPException(
            status_code=500,
            detail=f"Timeline query failed: {exc}",
        )
