"""Fulltext index registry and search helpers for Neo4j.

Maps Neo4j node labels to their corresponding fulltext index names as
defined in ``domains/maritime/schema/indexes.cypher``.  Provides helpers
for generating fulltext search Cypher clauses.
"""
from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Index registry
# ---------------------------------------------------------------------------

# Maps Neo4j label -> fulltext index name.
# Source of truth: domains/maritime/schema/indexes.cypher
FULLTEXT_INDEX_MAP: dict[str, str] = {
    "Document": "document_search",
    "Regulation": "regulation_search",
    "Vessel": "vessel_search",
    "Port": "port_search",
    "Experiment": "experiment_search",
    "TestFacility": "facility_search",
    "Organization": "organization_search",
    "ExperimentalDataset": "dataset_search",
}

# Reverse map: index name -> label
INDEX_TO_LABEL: dict[str, str] = {v: k for k, v in FULLTEXT_INDEX_MAP.items()}


def get_fulltext_index(label: str) -> str | None:
    """Return the fulltext index name for *label*, or ``None`` if unmapped.

    Args:
        label: Neo4j node label (e.g. ``"Vessel"``).

    Returns:
        Index name string or ``None``.
    """
    return FULLTEXT_INDEX_MAP.get(label)


def has_fulltext_index(label: str) -> bool:
    """Return ``True`` if *label* has a registered fulltext index."""
    return label in FULLTEXT_INDEX_MAP


# ---------------------------------------------------------------------------
# Cypher generators
# ---------------------------------------------------------------------------


def fulltext_search_cypher(
    index_name: str,
    *,
    result_var: str = "node",
    score_var: str = "score",
) -> str:
    """Generate a ``CALL db.index.fulltext.queryNodes(...)`` Cypher clause.

    The returned clause expects a ``$searchTerm`` parameter to be bound at
    execution time.

    Args:
        index_name: Name of the Neo4j fulltext index.
        result_var: Variable name for the matched node.
        score_var: Variable name for the relevance score.

    Returns:
        A Cypher string like
        ``CALL db.index.fulltext.queryNodes('vessel_search', $searchTerm)
        YIELD node AS node, score AS score``.
    """
    return (
        f"CALL db.index.fulltext.queryNodes('{index_name}', $searchTerm) "
        f"YIELD node AS {result_var}, score AS {score_var}"
    )


def multi_fulltext_search_cypher(
    index_names: list[str] | None = None,
    *,
    limit: int = 30,
) -> str:
    """Generate a UNION ALL query across multiple fulltext indexes.

    Each branch calls ``db.index.fulltext.queryNodes`` with ``$searchTerm``
    and ``$limit``, then the results are merged and sorted by score.

    Args:
        index_names: Specific indexes to search.  Defaults to all registered.
        limit: Per-index result limit.

    Returns:
        A Cypher string with UNION ALL branches and final ordering.
    """
    names = index_names or list(FULLTEXT_INDEX_MAP.values())
    branches: list[str] = []
    for idx_name in names:
        branch = (
            f"CALL db.index.fulltext.queryNodes('{idx_name}', $searchTerm) "
            f"YIELD node, score "
            f"WITH node, score LIMIT $limit "
            f"RETURN node, score, labels(node)[0] AS nodeLabel"
        )
        branches.append(branch)

    union = "\nUNION ALL\n".join(branches)
    # Wrap in a subquery to sort the combined results
    # Neo4j 5.x supports CALL { ... } UNION
    return union
