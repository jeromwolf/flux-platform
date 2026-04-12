"""Relationship CRUD endpoints for the Maritime KG API."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from kg.api.deps import get_async_neo4j_session, get_project_context
from kg.api.models import (
    CreateRelationshipRequest,
    EdgeResponse,
    RelationshipDetailResponse,
    RelationshipListResponse,
    UpdateRelationshipRequest,
)
from kg.api.routes.graph import _extract_node, _extract_relationship
from kg.api.serializers import serialize_neo4j_value
from kg.project import KGProjectContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/relationships", tags=["relationships"])


def _edge_dict_to_response(edge_dict: dict[str, Any]) -> EdgeResponse:
    """Convert an extracted relationship dict to an EdgeResponse.

    Args:
        edge_dict: Dict produced by :func:`_extract_relationship`.

    Returns:
        EdgeResponse instance.
    """
    return EdgeResponse(
        id=edge_dict["id"],
        type=edge_dict["type"],
        sourceId=edge_dict["sourceId"],
        targetId=edge_dict["targetId"],
        properties=edge_dict.get("properties", {}),
    )


@router.post("", response_model=RelationshipDetailResponse, status_code=201)
async def create_relationship(
    body: CreateRelationshipRequest,
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
    project: KGProjectContext = Depends(get_project_context),  # noqa: B008
) -> RelationshipDetailResponse:
    """Create a directed relationship between two existing nodes.

    Args:
        body: Source node ID, target node ID, relationship type, and
            optional properties.
        session: Async Neo4j session injected via FastAPI dependency.
        project: KG project context for multi-project isolation.

    Returns:
        RelationshipDetailResponse containing the relationship and both nodes.

    Raises:
        HTTPException: 404 if either source or target node does not exist.
        HTTPException: 500 if relationship creation fails.
    """
    rel_type = body.type  # already validated by Pydantic pattern
    cypher = (
        f"MATCH (a:{project.label}), (b:{project.label}) "
        f"WHERE elementId(a) = $src AND elementId(b) = $tgt "
        f"CREATE (a)-[r:{rel_type}]->(b) SET r += $props "
        f"RETURN r, a, b"
    )

    try:
        result = await session.run(
            cypher,
            {"src": body.sourceId, "tgt": body.targetId, "props": body.properties},
        )
        records = [record async for record in result]
    except Exception as exc:
        logger.exception("Failed to create relationship")
        raise HTTPException(
            status_code=500, detail=f"Relationship creation failed: {exc}"
        ) from exc

    if not records:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Source node '{body.sourceId}' or target node '{body.targetId}' not found"
            ),
        )

    record = records[0]
    edge_dict = _extract_relationship(record, "r")
    src_dict = _extract_node(record, "a")
    tgt_dict = _extract_node(record, "b")

    if edge_dict is None or src_dict is None or tgt_dict is None:
        raise HTTPException(
            status_code=500, detail="Failed to extract created relationship data"
        )

    from kg.api.models import NodeResponse  # avoid circular at module level

    return RelationshipDetailResponse(
        relationship=_edge_dict_to_response(edge_dict),
        sourceNode=NodeResponse(**src_dict),
        targetNode=NodeResponse(**tgt_dict),
    )


@router.get("/{rel_id}", response_model=RelationshipDetailResponse)
async def get_relationship(
    rel_id: str,
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
    project: KGProjectContext = Depends(get_project_context),  # noqa: B008
) -> RelationshipDetailResponse:
    """Retrieve a single relationship by its Neo4j element ID.

    Args:
        rel_id: The Neo4j element ID of the relationship.
        session: Async Neo4j session injected via FastAPI dependency.
        project: KG project context for multi-project isolation.

    Returns:
        RelationshipDetailResponse with the relationship and its endpoint nodes.

    Raises:
        HTTPException: 404 if no relationship with the given ID exists.
    """
    cypher = (
        f"MATCH (a:{project.label})-[r]->(b:{project.label}) WHERE elementId(r) = $id RETURN r, a, b"
    )

    result = await session.run(cypher, {"id": rel_id})
    records = [record async for record in result]

    if not records:
        raise HTTPException(
            status_code=404, detail=f"Relationship '{rel_id}' not found"
        )

    record = records[0]
    edge_dict = _extract_relationship(record, "r")
    src_dict = _extract_node(record, "a")
    tgt_dict = _extract_node(record, "b")

    if edge_dict is None or src_dict is None or tgt_dict is None:
        raise HTTPException(
            status_code=404, detail=f"Relationship '{rel_id}' not found"
        )

    from kg.api.models import NodeResponse

    return RelationshipDetailResponse(
        relationship=_edge_dict_to_response(edge_dict),
        sourceNode=NodeResponse(**src_dict),
        targetNode=NodeResponse(**tgt_dict),
    )


@router.put("/{rel_id}", response_model=EdgeResponse)
async def update_relationship(
    rel_id: str,
    body: UpdateRelationshipRequest,
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
    project: KGProjectContext = Depends(get_project_context),  # noqa: B008
) -> EdgeResponse:
    """Update properties of an existing relationship (merge semantics).

    Existing properties not present in the request body are preserved.

    Args:
        rel_id: The Neo4j element ID of the relationship to update.
        body: New property values to merge onto the relationship.
        session: Async Neo4j session injected via FastAPI dependency.
        project: KG project context for multi-project isolation.

    Returns:
        Updated EdgeResponse.

    Raises:
        HTTPException: 404 if no relationship with the given ID exists.
        HTTPException: 500 if the update operation fails.
    """
    cypher = (
        f"MATCH (:{project.label})-[r]->(:{project.label}) WHERE elementId(r) = $id SET r += $props RETURN r, "
        "startNode(r) AS a, endNode(r) AS b"
    )

    try:
        result = await session.run(cypher, {"id": rel_id, "props": body.properties})
        records = [record async for record in result]
    except Exception as exc:
        logger.exception("Failed to update relationship")
        raise HTTPException(
            status_code=500, detail=f"Relationship update failed: {exc}"
        ) from exc

    if not records:
        raise HTTPException(
            status_code=404, detail=f"Relationship '{rel_id}' not found"
        )

    record = records[0]
    edge_dict = _extract_relationship(record, "r")
    if edge_dict is None:
        raise HTTPException(
            status_code=404, detail=f"Relationship '{rel_id}' not found"
        )

    return _edge_dict_to_response(edge_dict)


@router.delete("/{rel_id}")
async def delete_relationship(
    rel_id: str,
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
    project: KGProjectContext = Depends(get_project_context),  # noqa: B008
) -> dict[str, Any]:
    """Delete a relationship by its Neo4j element ID.

    Args:
        rel_id: The Neo4j element ID of the relationship to delete.
        session: Async Neo4j session injected via FastAPI dependency.
        project: KG project context for multi-project isolation.

    Returns:
        Dict with ``deleted`` flag and ``relationshipId``.

    Raises:
        HTTPException: 404 if no relationship with the given ID exists.
        HTTPException: 500 if the delete operation fails.
    """
    # Check existence first
    check_cypher = (
        f"MATCH (:{project.label})-[r]->(:{project.label}) WHERE elementId(r) = $id RETURN count(r) AS cnt"
    )
    check_result = await session.run(check_cypher, {"id": rel_id})
    check_records = [record async for record in check_result]

    if not check_records:
        raise HTTPException(
            status_code=404, detail=f"Relationship '{rel_id}' not found"
        )

    cypher = f"MATCH (:{project.label})-[r]->(:{project.label}) WHERE elementId(r) = $id DELETE r"
    try:
        await session.run(cypher, {"id": rel_id})
    except Exception as exc:
        logger.exception("Failed to delete relationship")
        raise HTTPException(
            status_code=500, detail=f"Relationship deletion failed: {exc}"
        ) from exc

    return {"deleted": True, "relationshipId": rel_id}


@router.get("", response_model=RelationshipListResponse)
async def list_relationships(
    type: str | None = Query(  # noqa: A002
        default=None, description="Filter by relationship type"
    ),  # noqa: B008
    sourceId: str | None = Query(  # noqa: B008
        default=None, description="Filter by source node element ID"
    ),
    targetId: str | None = Query(  # noqa: B008
        default=None, description="Filter by target node element ID"
    ),
    limit: int = Query(  # noqa: B008
        default=50, ge=1, le=1000, description="Maximum relationships to return"
    ),
    offset: int = Query(default=0, ge=0, description="Number to skip"),  # noqa: B008
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
    project: KGProjectContext = Depends(get_project_context),  # noqa: B008
) -> RelationshipListResponse:
    """List relationships with optional filtering and pagination.

    Args:
        type: Optional relationship type filter.
        sourceId: Optional source node element ID filter.
        targetId: Optional target node element ID filter.
        limit: Maximum number of relationships to return (1–500).
        offset: Number of relationships to skip for pagination.
        session: Async Neo4j session injected via FastAPI dependency.

    Returns:
        RelationshipListResponse with paginated relationships and total count.
    """
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    conditions: list[str] = []

    rel_type_clause = ""
    if type is not None:
        rel_type_clause = f":{type}"

    if sourceId is not None:
        conditions.append("elementId(a) = $sourceId")
        params["sourceId"] = sourceId

    if targetId is not None:
        conditions.append("elementId(b) = $targetId")
        params["targetId"] = targetId

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    count_cypher = (
        f"MATCH (a:{project.label})-[r{rel_type_clause}]->(b:{project.label}) {where_clause} RETURN count(r) AS total"
    )
    count_result = await session.run(count_cypher, params)
    count_records = [record async for record in count_result]
    total = 0
    if count_records:
        try:
            total = count_records[0]["total"]
        except (KeyError, TypeError):
            total = 0

    list_cypher = (
        f"MATCH (a:{project.label})-[r{rel_type_clause}]->(b:{project.label}) {where_clause} "
        f"RETURN r SKIP $offset LIMIT $limit"
    )
    result = await session.run(list_cypher, params)
    records = [record async for record in result]

    edges: list[EdgeResponse] = []
    for record in records:
        edge_dict = _extract_relationship(record, "r")
        if edge_dict is not None:
            edges.append(_edge_dict_to_response(edge_dict))

    return RelationshipListResponse(
        relationships=edges, total=total, limit=limit, offset=offset
    )
