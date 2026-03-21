"""Cypher generators for GDS community detection algorithms.

Provides stream-mode Cypher generators for Louvain modularity and
Label Propagation community detection.  All functions return
``(cypher, params)`` tuples and do not require a Neo4j connection.

Usage::

    cypher, params = generate_louvain_cypher("vessel_graph", top_k=10)
    # rows: {name, communityId}

    cypher, params = generate_label_propagation_cypher(
        "vessel_graph", top_k=20
    )
    # rows: {name, communityId}
"""

from __future__ import annotations


def generate_louvain_cypher(
    projection: str,
    top_k: int = 10,
) -> tuple[str, dict]:
    """Generate a stream-mode Louvain community detection Cypher statement.

    Louvain optimises modularity to detect hierarchical community
    structure.  Each node is assigned a ``communityId``; nodes sharing
    the same id belong to the same detected community.

    Results are ordered by ``communityId`` ascending and limited to
    *top_k* rows, giving a representative sample across communities.

    Args:
        projection: Name of an existing GDS in-memory graph projection.
        top_k: Maximum number of result rows to return.
            Defaults to ``10``.

    Returns:
        A ``(cypher, params)`` tuple.  Result rows contain
        ``name`` (str) and ``communityId`` (int).
    """
    cypher = (
        "CALL gds.louvain.stream($projection) "
        "YIELD nodeId, communityId "
        "RETURN gds.util.asNode(nodeId).name AS name, communityId "
        "ORDER BY communityId "
        "LIMIT $topK"
    )
    params: dict = {
        "projection": projection,
        "topK": top_k,
    }
    return cypher, params


def generate_label_propagation_cypher(
    projection: str,
    top_k: int = 10,
) -> tuple[str, dict]:
    """Generate a stream-mode Label Propagation Cypher statement.

    Label Propagation assigns community labels by iteratively propagating
    the most frequent label among a node's neighbours.  It is fast and
    works well on large graphs with natural community structure.

    Args:
        projection: Name of an existing GDS in-memory graph projection.
        top_k: Maximum number of result rows to return.
            Defaults to ``10``.

    Returns:
        A ``(cypher, params)`` tuple.  Result rows contain
        ``name`` (str) and ``communityId`` (int).
    """
    cypher = (
        "CALL gds.labelPropagation.stream($projection) "
        "YIELD nodeId, communityId "
        "RETURN gds.util.asNode(nodeId).name AS name, communityId "
        "ORDER BY communityId "
        "LIMIT $topK"
    )
    params: dict = {
        "projection": projection,
        "topK": top_k,
    }
    return cypher, params
