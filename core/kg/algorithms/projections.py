"""Cypher generators for GDS in-memory graph projection lifecycle.

All methods return ``(cypher, params)`` tuples suitable for direct
execution against Neo4j via the standard driver.  No Neo4j connection
is required to call these methods.

Usage::

    manager = ProjectionManager()

    config = ProjectionConfig(
        name="vessel_graph",
        node_labels=["Vessel", "Port"],
        relationship_types=["DOCKED_AT"],
        orientation="UNDIRECTED",
    )

    cypher, params = manager.generate_create_cypher(config)
    # Execute: session.run(cypher, params)

    cypher, params = manager.generate_exists_cypher("vessel_graph")
    # Execute and inspect result["exists"]
"""

from __future__ import annotations

from kg.algorithms.models import ProjectionConfig


class ProjectionManager:
    """Generates GDS projection management Cypher statements.

    Each method returns a ``(cypher, params)`` tuple. The Cypher string
    uses ``$param`` placeholders; the dict provides the corresponding
    values. Pass both directly to ``session.run(cypher, params)``.
    """

    def generate_create_cypher(self, config: ProjectionConfig) -> tuple[str, dict]:
        """Generate a Cypher statement to create a named GDS graph projection.

        Projects the selected node labels and relationship types into GDS
        in-memory storage under the given projection name.  When
        ``node_labels`` or ``relationship_types`` is ``None`` the
        generated statement projects all labels / all relationship types.

        Args:
            config: Projection configuration specifying name, labels,
                relationship types, orientation, and optional properties.

        Returns:
            A ``(cypher, params)`` tuple.  The Cypher calls
            ``gds.graph.project`` with named parameters.
        """
        node_labels = config.node_labels if config.node_labels is not None else ["*"]
        rel_types = (
            config.relationship_types
            if config.relationship_types is not None
            else ["*"]
        )

        cypher = (
            "CALL gds.graph.project("
            "$name, "
            "$nodeLabels, "
            "$relTypes, "
            "{relationshipOrientation: $orient}"
            ")"
        )
        params: dict = {
            "name": config.name,
            "nodeLabels": node_labels,
            "relTypes": rel_types,
            "orient": config.orientation,
        }
        return cypher, params

    def generate_drop_cypher(self, name: str) -> tuple[str, dict]:
        """Generate a Cypher statement to drop an existing GDS projection.

        Uses ``failIfMissing = false`` so the call succeeds silently when
        the projection does not exist.

        Args:
            name: Name of the GDS projection to remove.

        Returns:
            A ``(cypher, params)`` tuple yielding ``graphName``.
        """
        cypher = "CALL gds.graph.drop($name, false) YIELD graphName"
        params: dict = {"name": name}
        return cypher, params

    def generate_exists_cypher(self, name: str) -> tuple[str, dict]:
        """Generate a Cypher statement to check whether a projection exists.

        Args:
            name: Name of the GDS projection to test.

        Returns:
            A ``(cypher, params)`` tuple.  The result row contains an
            ``exists`` boolean field.
        """
        cypher = "CALL gds.graph.exists($name) YIELD exists"
        params: dict = {"name": name}
        return cypher, params

    def generate_list_cypher(self) -> tuple[str, dict]:
        """Generate a Cypher statement to list all current GDS projections.

        Returns:
            A ``(cypher, params)`` tuple (params is empty).  Each result
            row contains ``graphName``, ``nodeCount``, and
            ``relationshipCount`` fields.
        """
        cypher = (
            "CALL gds.graph.list() "
            "YIELD graphName, nodeCount, relationshipCount"
        )
        return cypher, {}
