"""Cypher generators for GDS pathfinding algorithms.

Provides stream-mode Cypher generators for shortest-path and
weighted Dijkstra pathfinding.  All functions return
``(cypher, params)`` tuples and do not require a Neo4j connection.

Usage::

    cypher, params = generate_shortest_path_cypher(
        "vessel_graph",
        source_id="VESSEL-001",
        target_id="PORT-BUS",
    )
    # rows: {index, sourceNode, targetNode, totalCost, nodeIds, costs, path}

    cypher, params = generate_dijkstra_cypher(
        "vessel_graph",
        source_id="VESSEL-001",
        target_id="PORT-BUS",
        weight_property="distance",
    )
"""

from __future__ import annotations


def generate_shortest_path_cypher(
    projection: str,
    source_id: str,
    target_id: str,
) -> tuple[str, dict]:
    """Generate a Dijkstra single-source shortest-path Cypher statement.

    Finds the shortest (unweighted) path between *source_id* and
    *target_id* using the GDS Dijkstra implementation in stream mode.
    Nodes are matched on the ``id`` property.

    Args:
        projection: Name of an existing GDS in-memory graph projection.
        source_id: Value of the ``id`` property on the source node.
        target_id: Value of the ``id`` property on the target node.

    Returns:
        A ``(cypher, params)`` tuple.  Result rows contain GDS path
        fields: ``index``, ``sourceNode``, ``targetNode``,
        ``totalCost``, ``nodeIds``, ``costs``, and ``path``.
    """
    cypher = (
        "MATCH (source {id: $sourceId}), (target {id: $targetId}) "
        "CALL gds.shortestPath.dijkstra.stream($projection, "
        "{sourceNode: source, targetNode: target}) "
        "YIELD index, sourceNode, targetNode, totalCost, nodeIds, costs, path "
        "RETURN index, sourceNode, targetNode, totalCost, nodeIds, costs, path"
    )
    params: dict = {
        "projection": projection,
        "sourceId": source_id,
        "targetId": target_id,
    }
    return cypher, params


def generate_dijkstra_cypher(
    projection: str,
    source_id: str,
    target_id: str,
    weight_property: str = "weight",
) -> tuple[str, dict]:
    """Generate a weighted Dijkstra shortest-path Cypher statement.

    Like :func:`generate_shortest_path_cypher` but uses a relationship
    weight property so that the algorithm minimises total edge cost
    rather than hop count.

    Args:
        projection: Name of an existing GDS in-memory graph projection.
        source_id: Value of the ``id`` property on the source node.
        target_id: Value of the ``id`` property on the target node.
        weight_property: Relationship property to use as edge weight.
            Defaults to ``"weight"``.

    Returns:
        A ``(cypher, params)`` tuple.  Result rows contain GDS path
        fields: ``index``, ``sourceNode``, ``targetNode``,
        ``totalCost``, ``nodeIds``, ``costs``, and ``path``.
    """
    cypher = (
        "MATCH (source {id: $sourceId}), (target {id: $targetId}) "
        "CALL gds.shortestPath.dijkstra.stream($projection, "
        "{sourceNode: source, targetNode: target, "
        "relationshipWeightProperty: $weightProperty}) "
        "YIELD index, sourceNode, targetNode, totalCost, nodeIds, costs, path "
        "RETURN index, sourceNode, targetNode, totalCost, nodeIds, costs, path"
    )
    params: dict = {
        "projection": projection,
        "sourceId": source_id,
        "targetId": target_id,
        "weightProperty": weight_property,
    }
    return cypher, params
