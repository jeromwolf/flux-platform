"""Graph algorithm execution endpoints.

Provides REST API routes for running Neo4j GDS algorithms including
PageRank, community detection, centrality measures, pathfinding, and
node similarity.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from kg.api.deps import get_async_neo4j_session, get_project_context
from kg.api.models import (
    AlgorithmRequest,
    AlgorithmResponse,
    PageRankRequest,
    ShortestPathRequest,
    SimilarityRequest,
)
from kg.algorithms.runner import GDSAvailability, GraphAlgorithmRunner
from kg.project import KGProjectContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/algorithms", tags=["algorithms"])

# Module-level runner instance (shared across requests)
_runner = GraphAlgorithmRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _execute_algorithm(
    session: Any,
    algorithm: str,
    cypher: str,
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    """Execute an algorithm Cypher query and return serialized records.

    Args:
        session: Async Neo4j session.
        algorithm: Algorithm name for logging.
        cypher: Generated Cypher string.
        params: Parameters for the Cypher query.

    Returns:
        List of serialized result rows.

    Raises:
        HTTPException: 503 if GDS is not available.
        HTTPException: 500 if execution fails.
    """
    try:
        result = await session.run(cypher, params)
        records = [record async for record in result]
    except Exception as exc:
        err_str = str(exc)
        if "gds" in err_str.lower() or "procedure not found" in err_str.lower():
            raise HTTPException(
                status_code=503,
                detail="GDS plugin not available on this Neo4j instance",
            ) from exc
        logger.exception("Algorithm execution failed: %s", algorithm)
        raise HTTPException(
            status_code=500,
            detail=f"Algorithm '{algorithm}' execution failed: {exc}",
        ) from exc

    results: list[dict[str, Any]] = []
    for record in records:
        row: dict[str, Any] = {}
        if hasattr(record, "keys"):
            for key in record.keys():
                val = record[key]
                if hasattr(val, "element_id"):
                    row[key] = {
                        "id": val.element_id,
                        "labels": list(val.labels) if hasattr(val, "labels") else [],
                        "properties": dict(val),
                    }
                else:
                    row[key] = val
        results.append(row)
    return results


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_algorithms() -> dict[str, Any]:
    """List all supported GDS graph algorithms.

    Returns:
        Dict with ``algorithms`` list of supported algorithm name strings.
    """
    return {"algorithms": _runner.list_algorithms()}


@router.post("/pagerank", response_model=AlgorithmResponse)
async def run_pagerank(
    body: PageRankRequest,
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
    project: KGProjectContext = Depends(get_project_context),  # noqa: B008
) -> AlgorithmResponse:
    """Run PageRank centrality algorithm on an in-memory graph projection.

    Generates a GDS PageRank stream Cypher via
    :class:`~kg.algorithms.runner.GraphAlgorithmRunner` and optionally
    executes it against Neo4j.

    Args:
        body: Algorithm parameters including projection name, iterations, and damping.
        session: Async Neo4j session injected via FastAPI dependency.

    Returns:
        AlgorithmResponse with ranked nodes and generated Cypher.

    Raises:
        HTTPException: 503 if GDS is not available.
        HTTPException: 500 on execution failure.
    """
    projection = f"{body.label}_{body.relationshipType}_proj"
    cypher, params = _runner.generate_pagerank(
        projection,
        max_iterations=body.iterations,
        damping_factor=body.dampingFactor,
    )
    # NOTE: GDS algorithms operate on the full graph across all projects.
    # Project-scoped projections will be added when GDS supports label filtering.
    params["__kg_project_label"] = project.label

    results = await _execute_algorithm(session, "pagerank", cypher, params)

    return AlgorithmResponse(
        algorithm="pagerank",
        results=results,
        cypher=cypher,
        meta={
            "projection": projection,
            "label": body.label,
            "relationshipType": body.relationshipType,
            "iterations": body.iterations,
            "dampingFactor": body.dampingFactor,
        },
    )


@router.post("/community", response_model=AlgorithmResponse)
async def run_community_detection(
    body: AlgorithmRequest,
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
    project: KGProjectContext = Depends(get_project_context),  # noqa: B008
) -> AlgorithmResponse:
    """Run Louvain community detection algorithm.

    Uses Louvain modularity optimization to identify clusters of tightly
    connected nodes within the in-memory graph projection.

    Args:
        body: Algorithm parameters including label and relationship type.
        session: Async Neo4j session injected via FastAPI dependency.

    Returns:
        AlgorithmResponse with community assignments and generated Cypher.

    Raises:
        HTTPException: 503 if GDS is not available.
        HTTPException: 500 on execution failure.
    """
    projection = f"{body.label}_{body.relationshipType}_proj"
    cypher, params = _runner.generate_louvain(projection)
    # NOTE: GDS algorithms operate on the full graph across all projects.
    # Project-scoped projections will be added when GDS supports label filtering.
    params["__kg_project_label"] = project.label

    results = await _execute_algorithm(session, "louvain", cypher, params)

    return AlgorithmResponse(
        algorithm="louvain",
        results=results,
        cypher=cypher,
        meta={
            "projection": projection,
            "label": body.label,
            "relationshipType": body.relationshipType,
        },
    )


@router.post("/centrality", response_model=AlgorithmResponse)
async def run_centrality(
    body: AlgorithmRequest,
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
    project: KGProjectContext = Depends(get_project_context),  # noqa: B008
) -> AlgorithmResponse:
    """Run Betweenness Centrality algorithm.

    Computes how often each node lies on the shortest path between
    other node pairs, identifying bridge nodes in the graph.

    Args:
        body: Algorithm parameters including label and relationship type.
        session: Async Neo4j session injected via FastAPI dependency.

    Returns:
        AlgorithmResponse with centrality scores and generated Cypher.

    Raises:
        HTTPException: 503 if GDS is not available.
        HTTPException: 500 on execution failure.
    """
    projection = f"{body.label}_{body.relationshipType}_proj"
    cypher, params = _runner.generate_betweenness(projection)
    # NOTE: GDS algorithms operate on the full graph across all projects.
    # Project-scoped projections will be added when GDS supports label filtering.
    params["__kg_project_label"] = project.label

    results = await _execute_algorithm(session, "betweenness", cypher, params)

    return AlgorithmResponse(
        algorithm="betweenness",
        results=results,
        cypher=cypher,
        meta={
            "projection": projection,
            "label": body.label,
            "relationshipType": body.relationshipType,
        },
    )


@router.post("/shortest-path", response_model=AlgorithmResponse)
async def run_shortest_path(
    body: ShortestPathRequest,
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
    project: KGProjectContext = Depends(get_project_context),  # noqa: B008
) -> AlgorithmResponse:
    """Run Dijkstra shortest-path algorithm between two nodes.

    Finds the minimum-weight path between source and target nodes
    using the weighted Dijkstra implementation in GDS.

    Args:
        body: Path parameters including source ID, target ID, relationship type,
            and optional weight property.
        session: Async Neo4j session injected via FastAPI dependency.

    Returns:
        AlgorithmResponse with path nodes/cost and generated Cypher.

    Raises:
        HTTPException: 503 if GDS is not available.
        HTTPException: 500 on execution failure.
    """
    projection = f"{body.relationshipType}_path_proj"
    cypher, params = _runner.generate_dijkstra(
        projection,
        source_id=body.sourceId,
        target_id=body.targetId,
        weight_property=body.weightProperty,
    )
    # NOTE: GDS algorithms operate on the full graph across all projects.
    # Project-scoped projections will be added when GDS supports label filtering.
    params["__kg_project_label"] = project.label

    results = await _execute_algorithm(session, "dijkstra", cypher, params)

    return AlgorithmResponse(
        algorithm="dijkstra",
        results=results,
        cypher=cypher,
        meta={
            "projection": projection,
            "sourceId": body.sourceId,
            "targetId": body.targetId,
            "relationshipType": body.relationshipType,
            "weightProperty": body.weightProperty,
        },
    )


@router.post("/similarity", response_model=AlgorithmResponse)
async def run_node_similarity(
    body: SimilarityRequest,
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
    project: KGProjectContext = Depends(get_project_context),  # noqa: B008
) -> AlgorithmResponse:
    """Run Node Similarity algorithm (Jaccard coefficient).

    Identifies pairs of nodes that share common relationships and
    computes a similarity score based on Jaccard coefficient.

    Args:
        body: Algorithm parameters including label, relationship type, and topK.
        session: Async Neo4j session injected via FastAPI dependency.

    Returns:
        AlgorithmResponse with similar node pairs and generated Cypher.

    Raises:
        HTTPException: 503 if GDS is not available.
        HTTPException: 500 on execution failure.
    """
    projection = f"{body.label}_{body.relationshipType}_proj"
    cypher, params = _runner.generate_node_similarity(projection, top_k=body.topK)
    # NOTE: GDS algorithms operate on the full graph across all projects.
    # Project-scoped projections will be added when GDS supports label filtering.
    params["__kg_project_label"] = project.label

    results = await _execute_algorithm(session, "nodeSimilarity", cypher, params)

    return AlgorithmResponse(
        algorithm="nodeSimilarity",
        results=results,
        cypher=cypher,
        meta={
            "projection": projection,
            "label": body.label,
            "relationshipType": body.relationshipType,
            "topK": body.topK,
        },
    )


@router.get("/gds-status")
async def gds_status(
    session: Any = Depends(get_async_neo4j_session),  # noqa: B008
    project: KGProjectContext = Depends(get_project_context),  # noqa: B008
) -> dict[str, Any]:
    """Check whether the Neo4j GDS plugin is installed and return its version.

    Executes ``RETURN gds.version() AS version`` against Neo4j.  A
    successful result confirms GDS is available.

    Args:
        session: Async Neo4j session injected via FastAPI dependency.

    Returns:
        Dict with ``available`` (bool) and ``version`` (str or None).
    """
    cypher, params = GDSAvailability.generate_check_cypher()
    try:
        result = await session.run(cypher, params)
        records = [record async for record in result]
        version: str | None = None
        if records:
            try:
                version = records[0]["version"]
            except (KeyError, TypeError):
                version = None
        return {"available": True, "version": version}
    except Exception:
        logger.debug("GDS not available on this Neo4j instance", exc_info=True)
        return {"available": False, "version": None}
