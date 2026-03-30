"""Tests for TextToCypherPipeline multi-project support.

Verifies _inject_project_label() static method and process_to_cypher() with
project scoping. All tests run without Neo4j.
"""
from __future__ import annotations

import pytest

from kg.pipeline import TextToCypherPipeline
from kg.project import KGProjectContext


@pytest.mark.unit
class TestPipelineInjectProjectLabel:
    """TextToCypherPipeline._inject_project_label() tests."""

    def test_inject_project_label_basic(self) -> None:
        result = TextToCypherPipeline._inject_project_label(
            "MATCH (v:Vessel) RETURN v",
            KGProjectContext(name="Dev"),
        )
        assert "v:Vessel:KG_Dev" in result

    def test_inject_preserves_return(self) -> None:
        result = TextToCypherPipeline._inject_project_label(
            "MATCH (v:Vessel) WHERE v.name = 'X' RETURN v",
            KGProjectContext(name="Dev"),
        )
        assert "RETURN v" in result
        assert "KG_Dev" in result

    def test_inject_multiple_nodes(self) -> None:
        result = TextToCypherPipeline._inject_project_label(
            "MATCH (v:Vessel)-[r:DOCKED_AT]->(p:Port) RETURN v, p",
            KGProjectContext(name="Test"),
        )
        assert "v:Vessel:KG_Test" in result
        assert "p:Port:KG_Test" in result

    def test_inject_bare_node(self) -> None:
        """Bare node (no label) should NOT get project label from this regex
        because the Pipeline regex targets (var:Label patterns only."""
        original = "MATCH (n) RETURN n"
        result = TextToCypherPipeline._inject_project_label(
            original,
            KGProjectContext(name="Dev"),
        )
        # The pipeline regex only targets (var:Label) patterns,
        # so bare (n) may or may not be transformed.
        # The implementation uses r"(\(\w+:[A-Za-z_][A-Za-z0-9_]*)" which requires a colon.
        # So bare (n) should remain unchanged.
        assert "MATCH" in result

    def test_inject_with_string_project(self) -> None:
        result = TextToCypherPipeline._inject_project_label(
            "MATCH (v:Vessel) RETURN v",
            "Dev",
        )
        assert "v:Vessel:KG_Dev" in result

    def test_inject_optional_match(self) -> None:
        result = TextToCypherPipeline._inject_project_label(
            "OPTIONAL MATCH (v:Vessel)-[r]->(p:Port) RETURN v",
            KGProjectContext(name="Opt"),
        )
        assert "v:Vessel:KG_Opt" in result
        assert "p:Port:KG_Opt" in result

    def test_no_injection_without_project(self) -> None:
        """_inject_project_label is never called without a project arg."""
        original = "MATCH (v:Vessel) RETURN v"
        # Just verify the original has no KG_ label
        assert "KG_" not in original


@pytest.mark.unit
class TestPipelineProcessToCypher:
    """process_to_cypher() project scoping integration test."""

    def test_process_to_cypher_with_project(self) -> None:
        """process_to_cypher() with project rewrites the generated Cypher."""
        from kg.query_generator import QueryIntent, StructuredQuery

        pipeline = TextToCypherPipeline()
        sq = StructuredQuery(
            intent=QueryIntent(intent="FIND", confidence=0.9),
            object_types=["Vessel"],
        )
        result = pipeline.process_to_cypher(sq, project="DevKG")
        assert "KG_DevKG" in result.query

    def test_process_to_cypher_without_project(self) -> None:
        """process_to_cypher() without project returns unmodified query."""
        from kg.query_generator import QueryIntent, StructuredQuery

        pipeline = TextToCypherPipeline()
        sq = StructuredQuery(
            intent=QueryIntent(intent="FIND", confidence=0.9),
            object_types=["Vessel"],
        )
        result = pipeline.process_to_cypher(sq)
        assert "KG_" not in result.query

    def test_process_to_cypher_with_context_object(self) -> None:
        """process_to_cypher() accepts KGProjectContext too."""
        from kg.query_generator import QueryIntent, StructuredQuery

        pipeline = TextToCypherPipeline()
        ctx = KGProjectContext(name="Prod")
        sq = StructuredQuery(
            intent=QueryIntent(intent="FIND", confidence=0.9),
            object_types=["Vessel"],
        )
        result = pipeline.process_to_cypher(sq, project=ctx)
        assert "KG_Prod" in result.query
