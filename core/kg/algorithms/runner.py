"""High-level graph algorithm runner for Neo4j GDS.

Provides :class:`GraphAlgorithmRunner` as a unified facade over all
algorithm-specific Cypher generators, and :class:`GDSAvailability` to
verify that the GDS plugin is installed.

All ``generate_*`` methods return ``(cypher, params)`` tuples.  They
do not execute queries against Neo4j — callers are responsible for
passing the returned tuple to the Neo4j driver.

Usage::

    runner = GraphAlgorithmRunner()

    # Verify GDS is available (execute result against Neo4j)
    check_cypher, check_params = GDSAvailability.generate_check_cypher()

    # Generate algorithm Cypher
    cypher, params = runner.generate_pagerank("vessel_graph", top_k=5)
    cypher, params = runner.generate_louvain("vessel_graph")
    cypher, params = runner.generate_shortest_path(
        "vessel_graph", source_id="V-001", target_id="PORT-BUS"
    )

    # Projection lifecycle via the embedded manager
    create_cypher, create_params = runner.projection_manager.generate_create_cypher(config)
"""

from __future__ import annotations

from kg.algorithms.centrality import (
    generate_betweenness_cypher,
    generate_pagerank_cypher,
)
from kg.algorithms.community import (
    generate_label_propagation_cypher,
    generate_louvain_cypher,
)
from kg.algorithms.pathfinding import (
    generate_dijkstra_cypher,
    generate_shortest_path_cypher,
)
from kg.algorithms.projections import ProjectionManager
from kg.algorithms.similarity import generate_node_similarity_cypher

# ---------------------------------------------------------------------------
# GDS availability check
# ---------------------------------------------------------------------------

_SUPPORTED_ALGORITHMS: list[str] = [
    "pageRank",
    "betweenness",
    "louvain",
    "labelPropagation",
    "shortestPath",
    "dijkstra",
    "nodeSimilarity",
]


class GDSAvailability:
    """Helper for verifying Neo4j GDS plugin availability.

    The generated Cypher should be executed against the target Neo4j
    instance.  A successful result (no error) confirms GDS is installed
    and the version string is available.
    """

    @staticmethod
    def generate_check_cypher() -> tuple[str, dict]:
        """Generate a Cypher statement that returns the installed GDS version.

        Execute the returned Cypher against Neo4j.  If the call succeeds
        the ``version`` column contains the GDS version string (e.g.
        ``"2.6.0"``).  If GDS is not installed Neo4j raises a procedure
        not found error.

        Returns:
            A ``(cypher, params)`` tuple (params is empty).  The result
            row contains a ``version`` string field.
        """
        return "RETURN gds.version() AS version", {}


# ---------------------------------------------------------------------------
# Unified runner
# ---------------------------------------------------------------------------


class GraphAlgorithmRunner:
    """Unified facade for generating GDS algorithm Cypher statements.

    Aggregates all supported algorithm generators and delegates
    projection lifecycle operations to an internal
    :class:`~kg.algorithms.projections.ProjectionManager`.

    All ``generate_*`` methods accept a *projection* name plus
    optional algorithm-specific keyword arguments, and return
    ``(cypher, params)`` tuples ready to pass to the Neo4j driver.

    Args:
        projection_manager: Optional custom :class:`ProjectionManager`
            instance.  A default instance is created when not provided.

    Example::

        runner = GraphAlgorithmRunner()
        cypher, params = runner.generate_pagerank(
            "vessel_graph", max_iterations=30, top_k=20
        )
        # session.run(cypher, params)
    """

    def __init__(
        self,
        projection_manager: ProjectionManager | None = None,
    ) -> None:
        self._projection_manager = (
            projection_manager
            if projection_manager is not None
            else ProjectionManager()
        )

    # ------------------------------------------------------------------
    # Projection manager accessor
    # ------------------------------------------------------------------

    @property
    def projection_manager(self) -> ProjectionManager:
        """The internal :class:`ProjectionManager` instance."""
        return self._projection_manager

    # ------------------------------------------------------------------
    # Algorithm registry
    # ------------------------------------------------------------------

    def list_algorithms(self) -> list[str]:
        """Return the names of all supported GDS algorithms.

        Returns:
            Sorted list of algorithm name strings (e.g. ``["betweenness",
            "dijkstra", ...]``).
        """
        return sorted(_SUPPORTED_ALGORITHMS)

    # ------------------------------------------------------------------
    # Centrality algorithms
    # ------------------------------------------------------------------

    def generate_pagerank(
        self,
        projection: str,
        **kwargs,
    ) -> tuple[str, dict]:
        """Generate a stream-mode PageRank Cypher statement.

        Args:
            projection: Name of an existing GDS in-memory graph projection.
            **kwargs: Forwarded to
                :func:`~kg.algorithms.centrality.generate_pagerank_cypher`.
                Supported keys: ``max_iterations`` (int),
                ``damping_factor`` (float), ``top_k`` (int).

        Returns:
            A ``(cypher, params)`` tuple.
        """
        return generate_pagerank_cypher(projection, **kwargs)

    def generate_betweenness(
        self,
        projection: str,
        **kwargs,
    ) -> tuple[str, dict]:
        """Generate a stream-mode Betweenness Centrality Cypher statement.

        Args:
            projection: Name of an existing GDS in-memory graph projection.
            **kwargs: Forwarded to
                :func:`~kg.algorithms.centrality.generate_betweenness_cypher`.
                Supported keys: ``top_k`` (int).

        Returns:
            A ``(cypher, params)`` tuple.
        """
        return generate_betweenness_cypher(projection, **kwargs)

    # ------------------------------------------------------------------
    # Community detection algorithms
    # ------------------------------------------------------------------

    def generate_louvain(
        self,
        projection: str,
        **kwargs,
    ) -> tuple[str, dict]:
        """Generate a stream-mode Louvain community detection Cypher statement.

        Args:
            projection: Name of an existing GDS in-memory graph projection.
            **kwargs: Forwarded to
                :func:`~kg.algorithms.community.generate_louvain_cypher`.
                Supported keys: ``top_k`` (int).

        Returns:
            A ``(cypher, params)`` tuple.
        """
        return generate_louvain_cypher(projection, **kwargs)

    def generate_label_propagation(
        self,
        projection: str,
        **kwargs,
    ) -> tuple[str, dict]:
        """Generate a stream-mode Label Propagation Cypher statement.

        Args:
            projection: Name of an existing GDS in-memory graph projection.
            **kwargs: Forwarded to
                :func:`~kg.algorithms.community.generate_label_propagation_cypher`.
                Supported keys: ``top_k`` (int).

        Returns:
            A ``(cypher, params)`` tuple.
        """
        return generate_label_propagation_cypher(projection, **kwargs)

    # ------------------------------------------------------------------
    # Pathfinding algorithms
    # ------------------------------------------------------------------

    def generate_shortest_path(
        self,
        projection: str,
        source_id: str,
        target_id: str,
    ) -> tuple[str, dict]:
        """Generate a Dijkstra shortest-path Cypher statement (unweighted).

        Args:
            projection: Name of an existing GDS in-memory graph projection.
            source_id: Value of the ``id`` property on the source node.
            target_id: Value of the ``id`` property on the target node.

        Returns:
            A ``(cypher, params)`` tuple.
        """
        return generate_shortest_path_cypher(projection, source_id, target_id)

    def generate_dijkstra(
        self,
        projection: str,
        source_id: str,
        target_id: str,
        **kwargs,
    ) -> tuple[str, dict]:
        """Generate a weighted Dijkstra shortest-path Cypher statement.

        Args:
            projection: Name of an existing GDS in-memory graph projection.
            source_id: Value of the ``id`` property on the source node.
            target_id: Value of the ``id`` property on the target node.
            **kwargs: Forwarded to
                :func:`~kg.algorithms.pathfinding.generate_dijkstra_cypher`.
                Supported keys: ``weight_property`` (str).

        Returns:
            A ``(cypher, params)`` tuple.
        """
        return generate_dijkstra_cypher(projection, source_id, target_id, **kwargs)

    # ------------------------------------------------------------------
    # Similarity algorithms
    # ------------------------------------------------------------------

    def generate_node_similarity(
        self,
        projection: str,
        **kwargs,
    ) -> tuple[str, dict]:
        """Generate a stream-mode Node Similarity Cypher statement.

        Args:
            projection: Name of an existing GDS in-memory graph projection.
            **kwargs: Forwarded to
                :func:`~kg.algorithms.similarity.generate_node_similarity_cypher`.
                Supported keys: ``similarity_cutoff`` (float),
                ``top_k`` (int).

        Returns:
            A ``(cypher, params)`` tuple.
        """
        return generate_node_similarity_cypher(projection, **kwargs)
