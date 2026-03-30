"""Tests for fulltext search with project label filtering.

Verifies fulltext_search_cypher() and multi_fulltext_search_cypher() correctly
inject project_label WHERE clauses. All tests run without Neo4j.
"""
from __future__ import annotations

import pytest

from kg.fulltext import fulltext_search_cypher, multi_fulltext_search_cypher


@pytest.mark.unit
class TestFulltextProjectLabel:
    """fulltext_search_cypher() project_label tests."""

    def test_no_project_no_where(self) -> None:
        cypher = fulltext_search_cypher("vessel_search")
        assert "WHERE" not in cypher

    def test_with_project_adds_where(self) -> None:
        cypher = fulltext_search_cypher("vessel_search", project_label="KG_Dev")
        assert "WHERE node:KG_Dev" in cypher

    def test_custom_result_var(self) -> None:
        cypher = fulltext_search_cypher(
            "vessel_search", result_var="n", project_label="KG_Dev"
        )
        assert "WHERE n:KG_Dev" in cypher

    def test_score_var_unchanged(self) -> None:
        cypher = fulltext_search_cypher(
            "vessel_search", score_var="s", project_label="KG_Dev"
        )
        assert "score AS s" in cypher

    def test_index_name_in_call(self) -> None:
        cypher = fulltext_search_cypher("port_search", project_label="KG_X")
        assert "'port_search'" in cypher

    def test_search_term_param(self) -> None:
        cypher = fulltext_search_cypher("vessel_search", project_label="KG_Dev")
        assert "$searchTerm" in cypher


@pytest.mark.unit
class TestMultiFulltextProjectLabel:
    """multi_fulltext_search_cypher() project_label tests."""

    def test_multi_no_project(self) -> None:
        cypher = multi_fulltext_search_cypher(["vessel_search", "port_search"])
        assert "WHERE" not in cypher

    def test_multi_with_project(self) -> None:
        cypher = multi_fulltext_search_cypher(
            ["vessel_search", "port_search"], project_label="KG_Prod"
        )
        assert cypher.count("WHERE node:KG_Prod") == 2

    def test_multi_preserves_union(self) -> None:
        cypher = multi_fulltext_search_cypher(
            ["a", "b"], project_label="KG_X"
        )
        assert "UNION ALL" in cypher

    def test_multi_default_indexes(self) -> None:
        """With no explicit index_names, all registered indexes are used."""
        from kg.fulltext import FULLTEXT_INDEX_MAP

        cypher = multi_fulltext_search_cypher(project_label="KG_Y")
        for idx_name in FULLTEXT_INDEX_MAP.values():
            assert f"'{idx_name}'" in cypher

    def test_multi_each_branch_has_project(self) -> None:
        indexes = ["a", "b", "c"]
        cypher = multi_fulltext_search_cypher(indexes, project_label="KG_Z")
        assert cypher.count("WHERE node:KG_Z") == len(indexes)

    def test_multi_no_project_no_where_per_branch(self) -> None:
        cypher = multi_fulltext_search_cypher(["a", "b"])
        # Branches should NOT have WHERE clauses
        assert cypher.count("WHERE") == 0
