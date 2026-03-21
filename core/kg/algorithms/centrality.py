"""Cypher generators for GDS centrality algorithms.

Provides stream-mode Cypher generators for PageRank and Betweenness
Centrality.  All functions return ``(cypher, params)`` tuples and do
not require a Neo4j connection.

Usage::

    cypher, params = generate_pagerank_cypher(
        "vessel_graph",
        max_iterations=20,
        damping_factor=0.85,
        top_k=10,
    )
    # rows: {name, score}

    cypher, params = generate_betweenness_cypher("vessel_graph", top_k=5)
    # rows: {name, score}
"""

from __future__ import annotations


def generate_pagerank_cypher(
    projection: str,
    max_iterations: int = 20,
    damping_factor: float = 0.85,
    top_k: int = 10,
) -> tuple[str, dict]:
    """Generate a stream-mode PageRank Cypher statement.

    Streams PageRank scores for every node in the projection, ordered
    descending by score and limited to *top_k* rows.  Each result row
    exposes the node's ``name`` property and its computed ``score``.

    Args:
        projection: Name of an existing GDS in-memory graph projection.
        max_iterations: Maximum number of PageRank iterations.
            Higher values yield more precise scores at increased cost.
            Defaults to ``20``.
        damping_factor: Probability that a random walker continues
            following links (vs. teleporting to a random node).
            Must be in ``(0, 1)``. Defaults to ``0.85``.
        top_k: Number of top-scoring nodes to return.
            Defaults to ``10``.

    Returns:
        A ``(cypher, params)`` tuple.  Result rows contain
        ``name`` (str) and ``score`` (float).
    """
    cypher = (
        "CALL gds.pageRank.stream($projection, "
        "{maxIterations: $max, dampingFactor: $df}) "
        "YIELD nodeId, score "
        "RETURN gds.util.asNode(nodeId).name AS name, score "
        "ORDER BY score DESC "
        "LIMIT $topK"
    )
    params: dict = {
        "projection": projection,
        "max": max_iterations,
        "df": damping_factor,
        "topK": top_k,
    }
    return cypher, params


def generate_betweenness_cypher(
    projection: str,
    top_k: int = 10,
) -> tuple[str, dict]:
    """Generate a stream-mode Betweenness Centrality Cypher statement.

    Streams betweenness centrality scores for every node in the
    projection.  Nodes with high scores act as critical bridges on
    shortest paths between other node pairs.

    Args:
        projection: Name of an existing GDS in-memory graph projection.
        top_k: Number of highest-centrality nodes to return.
            Defaults to ``10``.

    Returns:
        A ``(cypher, params)`` tuple.  Result rows contain
        ``name`` (str) and ``score`` (float).
    """
    cypher = (
        "CALL gds.betweenness.stream($projection) "
        "YIELD nodeId, score "
        "RETURN gds.util.asNode(nodeId).name AS name, score "
        "ORDER BY score DESC "
        "LIMIT $topK"
    )
    params: dict = {
        "projection": projection,
        "topK": top_k,
    }
    return cypher, params
