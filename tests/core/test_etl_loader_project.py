"""Tests for Neo4jBatchLoader multi-project support.

Verifies that the loader generates correct MERGE Cypher with project labels
and _kg_project property stamps. All tests run without Neo4j.
"""
from __future__ import annotations

import pytest

from kg.etl.loader import Neo4jBatchLoader
from kg.project import KGProjectContext


@pytest.mark.unit
class TestBatchLoaderProject:
    """Neo4jBatchLoader project scoping tests."""

    def test_no_project_default_cypher(self) -> None:
        loader = Neo4jBatchLoader("Vessel", "vesselId")
        cypher = loader._build_merge_cypher()
        assert "KG_" not in cypher
        assert "_kg_project" not in cypher

    def test_project_string_adds_label(self) -> None:
        loader = Neo4jBatchLoader("Vessel", "vesselId", project="DevKG")
        cypher = loader._build_merge_cypher()
        assert ":KG_DevKG" in cypher
        assert "_kg_project" in cypher
        assert "'DevKG'" in cypher

    def test_project_context_adds_label(self) -> None:
        ctx = KGProjectContext(name="ProdKG")
        loader = Neo4jBatchLoader("Vessel", "vesselId", project=ctx)
        cypher = loader._build_merge_cypher()
        assert ":KG_ProdKG" in cypher
        assert "_kg_project" in cypher
        assert "'ProdKG'" in cypher

    def test_merge_pattern_includes_label(self) -> None:
        loader = Neo4jBatchLoader("Port", "portId", project="Test")
        cypher = loader._build_merge_cypher()
        assert "MERGE (n:Port:KG_Test" in cypher

    def test_set_includes_project_property(self) -> None:
        loader = Neo4jBatchLoader("Vessel", "vesselId", project="Dev")
        cypher = loader._build_merge_cypher()
        assert "n._kg_project = 'Dev'" in cypher

    def test_batch_size_unchanged(self) -> None:
        loader = Neo4jBatchLoader("Vessel", "vesselId", batch_size=100, project="X")
        assert loader.batch_size == 100

    def test_backward_compat_no_project(self) -> None:
        loader = Neo4jBatchLoader("Vessel", "vesselId", batch_size=200)
        cypher = loader._build_merge_cypher()
        assert "MERGE (n:Vessel" in cypher
        assert "KG_" not in cypher

    def test_label_order(self) -> None:
        """Domain label comes before project label in the MERGE pattern."""
        loader = Neo4jBatchLoader("Vessel", "vesselId", project="Dev")
        cypher = loader._build_merge_cypher()
        vessel_pos = cypher.index("Vessel")
        kg_pos = cypher.index("KG_Dev")
        assert vessel_pos < kg_pos

    def test_unwind_present(self) -> None:
        loader = Neo4jBatchLoader("Vessel", "vesselId", project="X")
        cypher = loader._build_merge_cypher()
        assert "UNWIND $batch AS row" in cypher

    def test_set_plus_equals_present(self) -> None:
        loader = Neo4jBatchLoader("Vessel", "vesselId", project="X")
        cypher = loader._build_merge_cypher()
        assert "SET n += row" in cypher

    def test_load_with_project_passes_cypher_to_session(self) -> None:
        """load() uses the project-scoped MERGE cypher against the session."""
        from unittest.mock import MagicMock

        loader = Neo4jBatchLoader("Vessel", "vesselId", project="Dev")
        session = MagicMock()
        records = [{"vesselId": "v1", "name": "Ship1"}]
        count = loader.load(records, session)
        assert count == 1
        call_cypher = session.run.call_args[0][0]
        assert "KG_Dev" in call_cypher
        assert "_kg_project" in call_cypher
