"""Node CRUD endpoints for the Maritime KG API."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from kg.api.deps import get_async_neo4j_session, get_project_context
from kg.api.models import (
    CreateNodeRequest,
    NodeListResponse,
    NodeResponse,
    UpdateNodeRequest,
)
from kg.api.routes.graph import _extract_node
from kg.api.serializers import serialize_neo4j_value
from kg.fulltext import fulltext_search_cypher, get_fulltext_index
from kg.project import KGProjectContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nodes", tags=["nodes"])


def _node_dict_to_response(node_dict: dict[str, Any]) -> NodeResponse:
    """Convert an extracted node dict to a NodeResponse.

    Args:
        node_dict: Dict produced by :func:`_extract_node`.

    Returns:
        NodeResponse instance.
    """
    return NodeResponse(
        id=node_dict["id"],
        labels=node_dict["labels"],
        primaryLabel=node_dict["primaryLabel"],
        group=node_dict["group"],
        color=node_dict["color"],
        properties=node_dict["properties"],
        displayName=node_dict["displayName"],
    )


@router.post("", response_model=NodeResponse, status_code=201)
async def create_node(
    body: CreateNodeRequest,
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
    project: KGProjectContext = Depends(get_project_context),  # noqa: B008
) -> NodeResponse:
    """Create a new node in the knowledge graph.

    Args:
        body: Labels and initial properties for the new node.
        session: Async Neo4j session injected via FastAPI dependency.
        project: KG project context for multi-project isolation.

    Returns:
        NodeResponse containing the created node.

    Raises:
        HTTPException: 422 if labels list is empty.
        HTTPException: 500 if node creation fails.
    """
    # Build label string — each label must be a valid identifier
    for label in body.labels:
        if not label.isidentifier():
            raise HTTPException(
                status_code=422,
                detail=f"Invalid label '{label}': must be a valid identifier",
            )

    label_str = ":".join(body.labels) + ":" + project.label
    props = {**body.properties, "_kg_project": project.property_value}
    cypher = f"CREATE (n:{label_str}) SET n += $props RETURN n"

    try:
        result = await session.run(cypher, {"props": props})
        records = [record async for record in result]
    except Exception as exc:
        logger.exception("Failed to create node")
        raise HTTPException(status_code=500, detail=f"Node creation failed: {exc}") from exc

    if not records:
        raise HTTPException(status_code=500, detail="Node creation returned no result")

    node_dict = _extract_node(records[0], "n")
    if node_dict is None:
        raise HTTPException(status_code=500, detail="Failed to extract created node")

    return _node_dict_to_response(node_dict)


@router.get("/{node_id}", response_model=NodeResponse)
async def get_node(
    node_id: str,
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
    project: KGProjectContext = Depends(get_project_context),  # noqa: B008
) -> NodeResponse:
    """Retrieve a single node by its Neo4j element ID.

    Args:
        node_id: The Neo4j element ID of the node.
        session: Async Neo4j session injected via FastAPI dependency.
        project: KG project context for multi-project isolation.

    Returns:
        NodeResponse for the matching node.

    Raises:
        HTTPException: 404 if no node with the given ID exists.
    """
    cypher = f"MATCH (n:{project.label}) WHERE elementId(n) = $id RETURN n"

    result = await session.run(cypher, {"id": node_id})
    records = [record async for record in result]

    if not records:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")

    node_dict = _extract_node(records[0], "n")
    if node_dict is None:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")

    return _node_dict_to_response(node_dict)


@router.put("/{node_id}", response_model=NodeResponse)
async def update_node(
    node_id: str,
    body: UpdateNodeRequest,
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
    project: KGProjectContext = Depends(get_project_context),  # noqa: B008
) -> NodeResponse:
    """Update properties of an existing node (merge semantics).

    Existing properties not present in the request body are preserved.

    Args:
        node_id: The Neo4j element ID of the node to update.
        body: New property values to merge onto the node.
        session: Async Neo4j session injected via FastAPI dependency.
        project: KG project context for multi-project isolation.

    Returns:
        NodeResponse with the updated node.

    Raises:
        HTTPException: 404 if no node with the given ID exists.
        HTTPException: 500 if the update operation fails.
    """
    cypher = f"MATCH (n:{project.label}) WHERE elementId(n) = $id SET n += $props RETURN n"

    try:
        result = await session.run(cypher, {"id": node_id, "props": body.properties})
        records = [record async for record in result]
    except Exception as exc:
        logger.exception("Failed to update node")
        raise HTTPException(status_code=500, detail=f"Node update failed: {exc}") from exc

    if not records:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")

    node_dict = _extract_node(records[0], "n")
    if node_dict is None:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")

    return _node_dict_to_response(node_dict)


@router.delete("/{node_id}")
async def delete_node(
    node_id: str,
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
    project: KGProjectContext = Depends(get_project_context),  # noqa: B008
) -> dict[str, Any]:
    """Delete a node and all its relationships.

    Uses ``DETACH DELETE`` to remove the node along with any attached
    relationships.

    Args:
        node_id: The Neo4j element ID of the node to delete.
        session: Async Neo4j session injected via FastAPI dependency.
        project: KG project context for multi-project isolation.

    Returns:
        Dict with ``deleted`` flag and ``nodeId``.

    Raises:
        HTTPException: 404 if no node with the given ID exists.
        HTTPException: 500 if the delete operation fails.
    """
    # First check the node exists
    check_cypher = f"MATCH (n:{project.label}) WHERE elementId(n) = $id RETURN count(n) AS cnt"
    check_result = await session.run(check_cypher, {"id": node_id})
    check_records = [record async for record in check_result]

    if not check_records:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")

    # Execute delete
    cypher = f"MATCH (n:{project.label}) WHERE elementId(n) = $id DETACH DELETE n"
    try:
        await session.run(cypher, {"id": node_id})
    except Exception as exc:
        logger.exception("Failed to delete node")
        raise HTTPException(status_code=500, detail=f"Node deletion failed: {exc}") from exc

    return {"deleted": True, "nodeId": node_id}


@router.get("", response_model=NodeListResponse)
async def list_nodes(
    label: str | None = Query(default=None, description="Filter by node label"),  # noqa: B008
    limit: int = Query(default=50, ge=1, le=1000, description="Maximum nodes to return"),  # noqa: B008
    offset: int = Query(default=0, ge=0, description="Number of nodes to skip"),  # noqa: B008
    q: str | None = Query(default=None, description="Search query (matches name/title)"),  # noqa: B008
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
    project: KGProjectContext = Depends(get_project_context),  # noqa: B008
) -> NodeListResponse:
    """List nodes with optional filtering and pagination.

    Args:
        label: Optional node label filter.
        limit: Maximum number of nodes to return (1–500).
        offset: Number of nodes to skip for pagination.
        q: Optional search string matched against name and title properties.
        session: Async Neo4j session injected via FastAPI dependency.

    Returns:
        NodeListResponse with paginated nodes and total count.

    Raises:
        HTTPException: 422 if label is not a valid identifier.
    """
    # Build WHERE clause
    conditions: list[str] = []
    params: dict[str, Any] = {"limit": limit, "offset": offset}

    label_clause = f":{project.label}"
    if label is not None:
        if not label.isidentifier():
            raise HTTPException(
                status_code=422,
                detail=f"Invalid label '{label}': must be a valid identifier",
            )
        label_clause = f":{label}:{project.label}"

    # Fulltext index search path — when label has a registered fulltext index
    fulltext_index = get_fulltext_index(label) if label else None

    if q is not None and fulltext_index is not None:
        # Use scored fulltext search instead of slow CONTAINS
        ft_call = fulltext_search_cypher(fulltext_index, result_var="n", score_var="ftScore")
        params["searchTerm"] = q

        # Add project label filter after fulltext YIELD
        conditions.append(f"n:{project.label}")
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        count_cypher = f"{ft_call} {where_clause} RETURN count(n) AS total"
        count_result = await session.run(count_cypher, params)
        count_records = [record async for record in count_result]
        total = 0
        if count_records:
            try:
                total = count_records[0]["total"]
            except (KeyError, TypeError):
                pass

        list_cypher = (
            f"{ft_call} {where_clause} "
            f"RETURN n ORDER BY ftScore DESC SKIP $skip LIMIT $limit"
        )
        params["skip"] = offset
        params["limit"] = limit
        result = await session.run(list_cypher, params)
        records = [record async for record in result]

        items: list[NodeResponse] = []
        for record in records:
            node_dict = _extract_node(record, "n")
            if node_dict is not None:
                items.append(_node_dict_to_response(node_dict))

        return NodeListResponse(nodes=items, total=total, limit=limit, offset=offset)

    elif q is not None:
        # Fallback: CONTAINS for labels without fulltext index
        conditions.append(
            "(n.name CONTAINS $q OR n.title CONTAINS $q OR n.nameEn CONTAINS $q)"
        )
        params["q"] = q

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    count_cypher = f"MATCH (n{label_clause}) {where_clause} RETURN count(n) AS total"
    count_result = await session.run(count_cypher, params)
    count_records = [record async for record in count_result]
    total = 0
    if count_records:
        try:
            total = count_records[0]["total"]
        except (KeyError, TypeError):
            total = 0

    list_cypher = (
        f"MATCH (n{label_clause}) {where_clause} RETURN n SKIP $offset LIMIT $limit"
    )
    result = await session.run(list_cypher, params)
    records = [record async for record in result]

    nodes: list[NodeResponse] = []
    for record in records:
        node_dict = _extract_node(record, "n")
        if node_dict is not None:
            nodes.append(_node_dict_to_response(node_dict))

    return NodeListResponse(nodes=nodes, total=total, limit=limit, offset=offset)
