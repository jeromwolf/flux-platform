"""Cypher Query Builder - Fluent API for constructing Neo4j Cypher queries.

Ported from flux-ontology-local's TypeScript CypherBuilder pattern.
Provides a type-safe, chainable interface for building Cypher queries.

Usage::
    from kg.cypher_builder import CypherBuilder

    # Simple query
    query, params = (
        CypherBuilder()
        .match("(v:Vessel)")
        .where("v.vesselType = $type", {"type": "ContainerShip"})
        .return_("v.name AS name, v.mmsi AS mmsi")
        .limit(10)
        .build()
    )

    # Using QueryOptions
    query, params = CypherBuilder.from_query_options(
        QueryOptions(
            type="Vessel",
            filter={"vesselType": {"equals": "ContainerShip"}},
            limit=10
        )
    ).build()
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass
class QueryFilter:
    """Filter specification for a single property."""

    equals: Any | None = None
    not_equals: Any | None = None
    contains: str | None = None
    starts_with: str | None = None
    ends_with: str | None = None
    gt: Any | None = None
    gte: Any | None = None
    lt: Any | None = None
    lte: Any | None = None
    in_: list[Any] | None = None
    not_in: list[Any] | None = None
    is_null: bool | None = None
    is_not_null: bool | None = None
    matches_regex: str | None = None


@dataclass
class QueryOptions:
    """Options for building a query from structured input."""

    type: str
    filter: dict[str, QueryFilter | dict[str, Any]] | None = None
    order_by: dict[str, Literal["asc", "desc"]] | None = None
    limit: int | None = None
    offset: int | None = None
    properties: list[str] | None = None


@dataclass
class SpatialQuery:
    """Spatial query specification."""

    center_lat: float
    center_lon: float
    radius_meters: float
    location_property: str = "location"


class CypherBuilder:
    """Fluent builder for constructing Neo4j Cypher queries.

    Provides a chainable API for building complex Cypher queries with
    proper parameter handling to prevent injection attacks.
    """

    def __init__(self) -> None:
        self._match_clauses: list[str] = []
        self._optional_match_clauses: list[str] = []
        self._where_clauses: list[str] = []
        self._return_clause: str = ""
        self._order_by_clause: str = ""
        self._limit_clause: str = ""
        self._skip_clause: str = ""
        self._with_clauses: list[str] = []
        self._call_clauses: list[str] = []
        self._parameters: dict[str, Any] = {}
        self._param_counter: int = 0

    def _next_param(self) -> str:
        """Generate next unique parameter name."""
        self._param_counter += 1
        return f"p{self._param_counter}"

    # =========================================================================
    # Basic Clauses
    # =========================================================================

    def match(self, pattern: str) -> CypherBuilder:
        """Add a MATCH clause.

        Args:
            pattern: Cypher pattern (e.g., "(n:Label)", "(a)-[:REL]->(b)")

        Returns:
            Self for chaining
        """
        self._match_clauses.append(f"MATCH {pattern}")
        return self

    def optional_match(self, pattern: str) -> CypherBuilder:
        """Add an OPTIONAL MATCH clause.

        Args:
            pattern: Cypher pattern

        Returns:
            Self for chaining
        """
        self._optional_match_clauses.append(f"OPTIONAL MATCH {pattern}")
        return self

    def where(self, condition: str, params: dict[str, Any] | None = None) -> CypherBuilder:
        """Add a WHERE condition.

        Args:
            condition: Cypher condition (e.g., "n.name = $name")
            params: Parameters to bind

        Returns:
            Self for chaining
        """
        self._where_clauses.append(condition)
        if params:
            self._parameters.update(params)
        return self

    def where_property(
        self,
        alias: str,
        property_name: str,
        filter_spec: QueryFilter | dict[str, Any],
    ) -> CypherBuilder:
        """Add WHERE conditions for a property filter.

        Args:
            alias: Node alias (e.g., "n", "v")
            property_name: Property to filter on
            filter_spec: Filter specification

        Returns:
            Self for chaining
        """
        if isinstance(filter_spec, dict):
            filter_spec = QueryFilter(**filter_spec)

        field = f"{alias}.{property_name}"

        if filter_spec.equals is not None:
            param = self._next_param()
            self._where_clauses.append(f"{field} = ${param}")
            self._parameters[param] = filter_spec.equals

        if filter_spec.not_equals is not None:
            param = self._next_param()
            self._where_clauses.append(f"{field} <> ${param}")
            self._parameters[param] = filter_spec.not_equals

        if filter_spec.contains is not None:
            param = self._next_param()
            self._where_clauses.append(f"{field} CONTAINS ${param}")
            self._parameters[param] = filter_spec.contains

        if filter_spec.starts_with is not None:
            param = self._next_param()
            self._where_clauses.append(f"{field} STARTS WITH ${param}")
            self._parameters[param] = filter_spec.starts_with

        if filter_spec.ends_with is not None:
            param = self._next_param()
            self._where_clauses.append(f"{field} ENDS WITH ${param}")
            self._parameters[param] = filter_spec.ends_with

        if filter_spec.gt is not None:
            param = self._next_param()
            self._where_clauses.append(f"{field} > ${param}")
            self._parameters[param] = filter_spec.gt

        if filter_spec.gte is not None:
            param = self._next_param()
            self._where_clauses.append(f"{field} >= ${param}")
            self._parameters[param] = filter_spec.gte

        if filter_spec.lt is not None:
            param = self._next_param()
            self._where_clauses.append(f"{field} < ${param}")
            self._parameters[param] = filter_spec.lt

        if filter_spec.lte is not None:
            param = self._next_param()
            self._where_clauses.append(f"{field} <= ${param}")
            self._parameters[param] = filter_spec.lte

        if filter_spec.in_ is not None:
            param = self._next_param()
            self._where_clauses.append(f"{field} IN ${param}")
            self._parameters[param] = filter_spec.in_

        if filter_spec.not_in is not None:
            param = self._next_param()
            self._where_clauses.append(f"NOT {field} IN ${param}")
            self._parameters[param] = filter_spec.not_in

        if filter_spec.is_null is True:
            self._where_clauses.append(f"{field} IS NULL")

        if filter_spec.is_not_null is True:
            self._where_clauses.append(f"{field} IS NOT NULL")

        if filter_spec.matches_regex is not None:
            param = self._next_param()
            self._where_clauses.append(f"{field} =~ ${param}")
            self._parameters[param] = filter_spec.matches_regex

        return self

    def with_(self, clause: str) -> CypherBuilder:
        """Add a WITH clause.

        Args:
            clause: WITH clause content

        Returns:
            Self for chaining
        """
        self._with_clauses.append(f"WITH {clause}")
        return self

    def call(self, procedure: str) -> CypherBuilder:
        """Add a CALL clause.

        Args:
            procedure: Procedure call (e.g., "db.index.fulltext.queryNodes(...)")

        Returns:
            Self for chaining
        """
        self._call_clauses.append(f"CALL {procedure}")
        return self

    def return_(self, clause: str) -> CypherBuilder:
        """Set the RETURN clause.

        Args:
            clause: RETURN clause content (without RETURN keyword)

        Returns:
            Self for chaining
        """
        self._return_clause = f"RETURN {clause}"
        return self

    def order_by(
        self,
        property_: str,
        direction: Literal["asc", "desc"] = "asc",
        alias: str = "n",
    ) -> CypherBuilder:
        """Add ORDER BY clause.

        Args:
            property_: Property to sort by
            direction: Sort direction
            alias: Node alias

        Returns:
            Self for chaining
        """
        dir_upper = direction.upper()
        sort_expr = f"{alias}.{property_} {dir_upper}"

        if self._order_by_clause:
            self._order_by_clause += f", {sort_expr}"
        else:
            self._order_by_clause = f"ORDER BY {sort_expr}"
        return self

    def limit(self, limit: int) -> CypherBuilder:
        """Set LIMIT clause.

        Args:
            limit: Maximum number of results

        Returns:
            Self for chaining
        """
        self._limit_clause = f"LIMIT {limit}"
        return self

    def skip(self, offset: int) -> CypherBuilder:
        """Set SKIP clause.

        Args:
            offset: Number of results to skip

        Returns:
            Self for chaining
        """
        self._skip_clause = f"SKIP {offset}"
        return self

    # =========================================================================
    # Spatial Queries
    # =========================================================================

    def where_within_distance(
        self,
        alias: str,
        location_property: str,
        center_lat: float,
        center_lon: float,
        radius_meters: float,
    ) -> CypherBuilder:
        """Add spatial distance filter.

        Args:
            alias: Node alias
            location_property: Property containing point()
            center_lat: Center latitude
            center_lon: Center longitude
            radius_meters: Radius in meters

        Returns:
            Self for chaining
        """
        param_lat = self._next_param()
        param_lon = self._next_param()
        param_radius = self._next_param()

        self._parameters[param_lat] = center_lat
        self._parameters[param_lon] = center_lon
        self._parameters[param_radius] = radius_meters

        condition = (
            f"point.distance({alias}.{location_property}, "
            f"point({{latitude: ${param_lat}, longitude: ${param_lon}}})) < ${param_radius}"
        )
        self._where_clauses.append(condition)
        return self

    def where_within_bounds(
        self,
        alias: str,
        location_property: str,
        min_lat: float,
        min_lon: float,
        max_lat: float,
        max_lon: float,
    ) -> CypherBuilder:
        """Add bounding box spatial filter.

        Args:
            alias: Node alias
            location_property: Property containing point()
            min_lat: Minimum latitude
            min_lon: Minimum longitude
            max_lat: Maximum latitude
            max_lon: Maximum longitude

        Returns:
            Self for chaining
        """
        field = f"{alias}.{location_property}"

        p_min_lat = self._next_param()
        p_max_lat = self._next_param()
        p_min_lon = self._next_param()
        p_max_lon = self._next_param()

        self._parameters[p_min_lat] = min_lat
        self._parameters[p_max_lat] = max_lat
        self._parameters[p_min_lon] = min_lon
        self._parameters[p_max_lon] = max_lon

        conditions = [
            f"{field}.latitude >= ${p_min_lat}",
            f"{field}.latitude <= ${p_max_lat}",
            f"{field}.longitude >= ${p_min_lon}",
            f"{field}.longitude <= ${p_max_lon}",
        ]
        self._where_clauses.extend(conditions)
        return self

    # =========================================================================
    # Build
    # =========================================================================

    def build(self) -> tuple[str, dict[str, Any]]:
        """Build the final Cypher query.

        Returns:
            Tuple of (query_string, parameters_dict)
        """
        parts: list[str] = []

        # CALL clauses first (for procedures like fulltext search)
        parts.extend(self._call_clauses)

        # MATCH clauses
        parts.extend(self._match_clauses)

        # OPTIONAL MATCH clauses
        parts.extend(self._optional_match_clauses)

        # WHERE clause
        if self._where_clauses:
            parts.append(f"WHERE {' AND '.join(self._where_clauses)}")

        # WITH clauses
        parts.extend(self._with_clauses)

        # RETURN clause
        if self._return_clause:
            parts.append(self._return_clause)

        # ORDER BY
        if self._order_by_clause:
            parts.append(self._order_by_clause)

        # SKIP
        if self._skip_clause:
            parts.append(self._skip_clause)

        # LIMIT
        if self._limit_clause:
            parts.append(self._limit_clause)

        return "\n".join(parts), self._parameters

    # =========================================================================
    # Static Factory Methods
    # =========================================================================

    @classmethod
    def from_query_options(cls, options: QueryOptions) -> CypherBuilder:
        """Create a CypherBuilder from QueryOptions.

        Args:
            options: Structured query options

        Returns:
            Configured CypherBuilder
        """
        builder = cls()
        alias = options.type.lower()[0]

        # MATCH clause
        builder.match(f"({alias}:{options.type})")

        # WHERE clauses from filter
        if options.filter:
            for prop, filter_spec in options.filter.items():
                builder.where_property(alias, prop, filter_spec)

        # ORDER BY
        if options.order_by:
            for prop, direction in options.order_by.items():
                builder.order_by(prop, direction, alias)

        # SKIP/LIMIT
        if options.offset is not None:
            builder.skip(options.offset)
        if options.limit is not None:
            builder.limit(options.limit)

        # RETURN clause
        if options.properties:
            props = ", ".join(f"{alias}.{p} AS {p}" for p in options.properties)
            builder.return_(props)
        else:
            builder.return_(alias)

        return builder

    @classmethod
    def find_related_objects(
        cls,
        object_id: str,
        relationship_type: str,
        direction: Literal["outgoing", "incoming", "both"] = "both",
    ) -> tuple[str, dict[str, Any]]:
        """Build query to find related objects.

        Args:
            object_id: ID of the source object
            relationship_type: Relationship type to traverse
            direction: Relationship direction

        Returns:
            Tuple of (query_string, parameters_dict)
        """
        if direction == "outgoing":
            pattern = f"(n {{id: $objectId}})-[:{relationship_type}]->(related)"
        elif direction == "incoming":
            pattern = f"(n {{id: $objectId}})<-[:{relationship_type}]-(related)"
        else:
            pattern = f"(n {{id: $objectId}})-[:{relationship_type}]-(related)"

        query = f"MATCH {pattern}\nRETURN related"
        return query, {"objectId": object_id}

    @classmethod
    def find_shortest_path(
        cls,
        from_id: str,
        to_id: str,
        max_depth: int = 5,
    ) -> tuple[str, dict[str, Any]]:
        """Build query to find shortest path between two nodes.

        Args:
            from_id: Source node ID
            to_id: Target node ID
            max_depth: Maximum path length

        Returns:
            Tuple of (query_string, parameters_dict)
        """
        query = f"""
MATCH p = shortestPath((from {{id: $fromId}})-[*..{max_depth}]-(to {{id: $toId}}))
RETURN p
        """.strip()
        return query, {"fromId": from_id, "toId": to_id}

    @classmethod
    def get_subgraph(
        cls,
        root_id: str,
        depth: int = 2,
        relationship_types: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Build query to get subgraph around a node.

        Requires APOC plugin.

        Args:
            root_id: Root node ID
            depth: Maximum depth to traverse
            relationship_types: Optional list of relationship types to include

        Returns:
            Tuple of (query_string, parameters_dict)
        """
        rel_pattern = "|".join(relationship_types) if relationship_types else ""

        query = f"""
MATCH (root {{id: $rootId}})
CALL apoc.path.subgraphAll(root, {{
  maxLevel: {depth},
  relationshipFilter: "{rel_pattern}"
}})
YIELD nodes, relationships
RETURN nodes, relationships
        """.strip()
        return query, {"rootId": root_id}

    @classmethod
    def fulltext_search(
        cls,
        index_name: str,
        search_term: str,
        limit: int = 10,
    ) -> tuple[str, dict[str, Any]]:
        """Build fulltext search query.

        Args:
            index_name: Fulltext index name
            search_term: Search term
            limit: Maximum results

        Returns:
            Tuple of (query_string, parameters_dict)
        """
        query = f"""
CALL db.index.fulltext.queryNodes($indexName, $searchTerm)
YIELD node, score
RETURN node, score
ORDER BY score DESC
LIMIT {limit}
        """.strip()
        return query, {"indexName": index_name, "searchTerm": search_term}

    @classmethod
    def nearby_entities(
        cls,
        entity_type: str,
        center_lat: float,
        center_lon: float,
        radius_km: float,
        location_property: str = "location",
        limit: int = 20,
    ) -> tuple[str, dict[str, Any]]:
        """Build query for nearby entities.

        Args:
            entity_type: Node label
            center_lat: Center latitude
            center_lon: Center longitude
            radius_km: Radius in kilometers
            location_property: Property containing point()
            limit: Maximum results

        Returns:
            Tuple of (query_string, parameters_dict)
        """
        alias = entity_type.lower()[0]
        radius_meters = radius_km * 1000

        query = f"""
MATCH ({alias}:{entity_type})
WHERE point.distance({alias}.{location_property}, point({{latitude: $lat, longitude: $lon}})) < $radius
WITH {alias}, point.distance({alias}.{location_property}, point({{latitude: $lat, longitude: $lon}})) AS distance
RETURN {alias}, round(distance / 1000.0, 2) AS distance_km
ORDER BY distance
LIMIT {limit}
        """.strip()

        return query, {"lat": center_lat, "lon": center_lon, "radius": radius_meters}
