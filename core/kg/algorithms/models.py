"""Data models for Neo4j GDS graph algorithm operations.

Provides frozen dataclasses for configuring graph projections and
representing algorithm execution results.

Usage::

    config = ProjectionConfig(
        name="my_graph",
        node_labels=["Vessel", "Port"],
        relationship_types=["DOCKED_AT"],
    )

    result = AlgorithmResult(
        algorithm="pageRank",
        projection_name="my_graph",
        node_count=42,
        results=[{"name": "BusanPort", "score": 0.9}],
    )
    assert result.success
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProjectionConfig:
    """Configuration for a named GDS in-memory graph projection.

    A projection selects a subset of the Neo4j graph (nodes and
    relationships) to load into GDS memory for algorithm execution.

    Attributes:
        name: Unique projection name used to reference it in GDS calls.
        node_labels: Node labels to include. ``None`` projects all labels
            (equivalent to ``"*"`` in GDS syntax).
        relationship_types: Relationship types to include. ``None`` projects
            all types (equivalent to ``"*"`` in GDS syntax).
        orientation: Relationship orientation strategy. Must be one of:
            ``"NATURAL"`` (follow stored direction), ``"REVERSE"``
            (reverse stored direction), or ``"UNDIRECTED"`` (project both
            directions). Defaults to ``"NATURAL"``.
        properties: Node property names to load into the projection for
            use as algorithm weights or features. ``None`` loads no
            additional properties.
    """

    name: str
    node_labels: list[str] | None = None
    relationship_types: list[str] | None = None
    orientation: str = "NATURAL"
    properties: list[str] | None = None


@dataclass(frozen=True)
class AlgorithmResult:
    """Result of a GDS algorithm execution.

    Aggregates metadata and per-node results from a stream-mode GDS
    algorithm run. The ``success`` property reflects whether any errors
    were recorded.

    Attributes:
        algorithm: Algorithm identifier (e.g., ``"pageRank"``,
            ``"louvain"``).
        projection_name: Name of the GDS projection that was used.
        node_count: Number of nodes processed by the algorithm.
        relationship_count: Number of relationships processed.
        compute_millis: Wall-clock time spent in GDS computation (ms).
        results: Per-node result rows as plain dicts (keys vary by
            algorithm, e.g. ``{"name": "...", "score": 0.9}``).
        errors: Error messages collected during execution. Non-empty
            implies ``success == False``.
    """

    algorithm: str
    projection_name: str
    node_count: int = 0
    relationship_count: int = 0
    compute_millis: int = 0
    results: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """True when no errors were recorded during algorithm execution."""
        return len(self.errors) == 0
