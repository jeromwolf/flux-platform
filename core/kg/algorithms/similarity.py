"""Cypher generators for GDS node similarity algorithms.

Provides a stream-mode Cypher generator for Node Similarity based on
shared neighbours (Jaccard / overlap coefficient).  All functions
return ``(cypher, params)`` tuples and do not require a Neo4j
connection.

Usage::

    cypher, params = generate_node_similarity_cypher(
        "vessel_graph",
        similarity_cutoff=0.5,
        top_k=10,
    )
    # rows: {node1Name, node2Name, similarity}
"""

from __future__ import annotations


def generate_node_similarity_cypher(
    projection: str,
    similarity_cutoff: float = 0.5,
    top_k: int = 10,
) -> tuple[str, dict]:
    """Generate a stream-mode Node Similarity Cypher statement.

    Computes pairwise Jaccard similarity between nodes that share
    common neighbours.  Only pairs with a similarity score at or above
    *similarity_cutoff* are returned, and at most *top_k* neighbour
    pairs per node are considered (``topK`` GDS parameter).

    Args:
        projection: Name of an existing GDS in-memory graph projection.
        similarity_cutoff: Minimum Jaccard similarity score (0.0–1.0)
            required for a pair to be included in the results.
            Defaults to ``0.5``.
        top_k: Maximum number of similar neighbours to return per node
            (GDS ``topK`` parameter).  Defaults to ``10``.

    Returns:
        A ``(cypher, params)`` tuple.  Result rows contain
        ``node1Name`` (str), ``node2Name`` (str), and
        ``similarity`` (float).
    """
    cypher = (
        "CALL gds.nodeSimilarity.stream($projection, "
        "{similarityCutoff: $cutoff, topK: $topK}) "
        "YIELD node1, node2, similarity "
        "RETURN "
        "gds.util.asNode(node1).name AS node1Name, "
        "gds.util.asNode(node2).name AS node2Name, "
        "similarity "
        "ORDER BY similarity DESC "
        "LIMIT $topK"
    )
    params: dict = {
        "projection": projection,
        "cutoff": similarity_cutoff,
        "topK": top_k,
    }
    return cypher, params
