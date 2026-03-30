"""Tests for CypherBuilder multi-project scoping.

Verifies for_project(), _inject_project_label(), and project_label parameters
on all static factory methods. All tests run without Neo4j.
"""
from __future__ import annotations

import pytest

from kg.cypher_builder import CypherBuilder, QueryOptions
from kg.project import KGProjectContext


# ---------------------------------------------------------------------------
# for_project() fluent method
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestForProject:
    """CypherBuilder.for_project() tests."""

    def test_for_project_string(self) -> None:
        query, _ = (
            CypherBuilder()
            .match("(n:Vessel)")
            .for_project("DevKG")
            .return_("n")
            .build()
        )
        assert "n:Vessel:KG_DevKG" in query

    def test_for_project_context(self) -> None:
        ctx = KGProjectContext(name="ProdKG")
        query, _ = (
            CypherBuilder()
            .match("(n:Vessel)")
            .for_project(ctx)
            .return_("n")
            .build()
        )
        assert "n:Vessel:KG_ProdKG" in query

    def test_no_project_unchanged(self) -> None:
        query, _ = (
            CypherBuilder()
            .match("(n:Vessel)")
            .return_("n")
            .build()
        )
        assert "KG_" not in query
        assert "(n:Vessel)" in query

    def test_bare_node_gets_label(self) -> None:
        query, _ = (
            CypherBuilder()
            .match("(n)")
            .for_project("Dev")
            .return_("n")
            .build()
        )
        assert "n:KG_Dev" in query

    def test_relationship_pattern_both_nodes(self) -> None:
        query, _ = (
            CypherBuilder()
            .match("(a:Vessel)-[r:DOCKED_AT]->(b:Port)")
            .for_project("Dev")
            .return_("a, r, b")
            .build()
        )
        assert "a:Vessel:KG_Dev" in query
        assert "b:Port:KG_Dev" in query

    def test_optional_match_injected(self) -> None:
        query, _ = (
            CypherBuilder()
            .match("(n:Vessel)")
            .optional_match("(n)-[r]->(m:Port)")
            .for_project("Test")
            .return_("n, r, m")
            .build()
        )
        assert "n:Vessel:KG_Test" in query
        assert "m:Port:KG_Test" in query

    def test_where_preserved(self) -> None:
        query, params = (
            CypherBuilder()
            .match("(n:Vessel)")
            .where("n.name = $name", {"name": "Test"})
            .for_project("Dev")
            .return_("n")
            .build()
        )
        assert "n:Vessel:KG_Dev" in query
        assert "WHERE n.name = $name" in query
        assert params["name"] == "Test"

    def test_chaining_order_irrelevant(self) -> None:
        """for_project can be called before or after match -- same result."""
        q1, _ = (
            CypherBuilder()
            .for_project("X")
            .match("(n:Vessel)")
            .return_("n")
            .build()
        )
        q2, _ = (
            CypherBuilder()
            .match("(n:Vessel)")
            .for_project("X")
            .return_("n")
            .build()
        )
        assert q1 == q2

    def test_multiple_match_clauses(self) -> None:
        """Both MATCH clauses get the project label."""
        query, _ = (
            CypherBuilder()
            .match("(a:Vessel)")
            .match("(b:Port)")
            .for_project("Multi")
            .return_("a, b")
            .build()
        )
        assert "a:Vessel:KG_Multi" in query
        assert "b:Port:KG_Multi" in query


# ---------------------------------------------------------------------------
# _inject_project_label static method
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestInjectProjectLabel:
    """CypherBuilder._inject_project_label() static method tests."""

    def test_single_labeled_node(self) -> None:
        result = CypherBuilder._inject_project_label(
            "MATCH (v:Vessel)", "KG_Dev"
        )
        assert "v:Vessel:KG_Dev" in result

    def test_bare_node(self) -> None:
        result = CypherBuilder._inject_project_label(
            "MATCH (n)", "KG_Dev"
        )
        assert "n:KG_Dev" in result

    def test_relationship_pattern(self) -> None:
        result = CypherBuilder._inject_project_label(
            "MATCH (a:Vessel)-[r:REL]->(b:Port)", "KG_X"
        )
        assert "a:Vessel:KG_X" in result
        assert "b:Port:KG_X" in result

    def test_does_not_modify_relationship_types(self) -> None:
        result = CypherBuilder._inject_project_label(
            "MATCH (a:Vessel)-[r:DOCKED_AT]->(b:Port)", "KG_Y"
        )
        assert "[r:DOCKED_AT]" in result
        # Relationship alias should NOT get a project label
        assert "r:DOCKED_AT:KG_Y" not in result


# ---------------------------------------------------------------------------
# from_query_options with project
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFromQueryOptionsProject:
    """from_query_options with project parameter."""

    def test_with_project_string(self) -> None:
        opts = QueryOptions(type="Vessel", limit=10)
        query, _ = CypherBuilder.from_query_options(opts, project="DevKG").build()
        assert "KG_DevKG" in query

    def test_with_project_context(self) -> None:
        opts = QueryOptions(type="Port")
        ctx = KGProjectContext(name="Prod")
        query, _ = CypherBuilder.from_query_options(opts, project=ctx).build()
        assert "KG_Prod" in query

    def test_without_project(self) -> None:
        opts = QueryOptions(type="Vessel")
        query, _ = CypherBuilder.from_query_options(opts).build()
        assert "KG_" not in query


# ---------------------------------------------------------------------------
# Static factory methods with project_label
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestStaticMethodsProject:
    """Static factory methods with project_label parameter."""

    def test_find_related_objects_with_project(self) -> None:
        query, _ = CypherBuilder.find_related_objects(
            "id1", "DOCKED_AT", project_label="KG_Dev"
        )
        assert "KG_Dev" in query

    def test_find_related_objects_without_project(self) -> None:
        query, _ = CypherBuilder.find_related_objects("id1", "DOCKED_AT")
        assert "KG_" not in query

    def test_find_related_objects_outgoing_with_project(self) -> None:
        query, _ = CypherBuilder.find_related_objects(
            "id1", "DOCKED_AT", direction="outgoing", project_label="KG_Dev"
        )
        assert ":KG_Dev" in query
        assert "-[:DOCKED_AT]->" in query

    def test_find_related_objects_incoming_with_project(self) -> None:
        query, _ = CypherBuilder.find_related_objects(
            "id1", "DOCKED_AT", direction="incoming", project_label="KG_Dev"
        )
        assert ":KG_Dev" in query
        assert "<-[:DOCKED_AT]-" in query

    def test_find_shortest_path_with_project(self) -> None:
        query, _ = CypherBuilder.find_shortest_path("a", "b", project_label="KG_Dev")
        assert "KG_Dev" in query

    def test_find_shortest_path_without_project(self) -> None:
        query, _ = CypherBuilder.find_shortest_path("a", "b")
        assert "KG_" not in query

    def test_get_subgraph_with_project(self) -> None:
        query, _ = CypherBuilder.get_subgraph("root1", project_label="KG_Test")
        assert "KG_Test" in query

    def test_get_subgraph_without_project(self) -> None:
        query, _ = CypherBuilder.get_subgraph("root1")
        assert "KG_" not in query

    def test_fulltext_search_with_project(self) -> None:
        query, _ = CypherBuilder.fulltext_search(
            "vessel_search", "test", project_label="KG_Dev"
        )
        assert "WHERE node:KG_Dev" in query

    def test_fulltext_search_without_project(self) -> None:
        query, _ = CypherBuilder.fulltext_search("vessel_search", "test")
        assert "WHERE" not in query

    def test_nearby_entities_with_project(self) -> None:
        query, _ = CypherBuilder.nearby_entities(
            "Vessel", 35.0, 129.0, 10.0, project_label="KG_Dev"
        )
        assert "KG_Dev" in query

    def test_nearby_entities_without_project(self) -> None:
        query, _ = CypherBuilder.nearby_entities("Vessel", 35.0, 129.0, 10.0)
        assert "KG_" not in query
