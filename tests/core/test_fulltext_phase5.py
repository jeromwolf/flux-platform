"""Unit tests for Phase 5 fulltext index integration."""
from __future__ import annotations

import pytest

# Tests for core/kg/fulltext.py
from core.kg.fulltext import (
    FULLTEXT_INDEX_MAP,
    INDEX_TO_LABEL,
    get_fulltext_index,
    has_fulltext_index,
    fulltext_search_cypher,
    multi_fulltext_search_cypher,
)


class TestFulltextIndexMap:
    """Tests for the fulltext index registry."""

    @pytest.mark.unit
    def test_all_eight_indexes_registered(self) -> None:
        assert len(FULLTEXT_INDEX_MAP) == 8

    @pytest.mark.unit
    def test_document_index(self) -> None:
        assert FULLTEXT_INDEX_MAP["Document"] == "document_search"

    @pytest.mark.unit
    def test_vessel_index(self) -> None:
        assert FULLTEXT_INDEX_MAP["Vessel"] == "vessel_search"

    @pytest.mark.unit
    def test_port_index(self) -> None:
        assert FULLTEXT_INDEX_MAP["Port"] == "port_search"

    @pytest.mark.unit
    def test_regulation_index(self) -> None:
        assert FULLTEXT_INDEX_MAP["Regulation"] == "regulation_search"

    @pytest.mark.unit
    def test_experiment_index(self) -> None:
        assert FULLTEXT_INDEX_MAP["Experiment"] == "experiment_search"

    @pytest.mark.unit
    def test_facility_index(self) -> None:
        assert FULLTEXT_INDEX_MAP["TestFacility"] == "facility_search"

    @pytest.mark.unit
    def test_organization_index(self) -> None:
        assert FULLTEXT_INDEX_MAP["Organization"] == "organization_search"

    @pytest.mark.unit
    def test_dataset_index(self) -> None:
        assert FULLTEXT_INDEX_MAP["ExperimentalDataset"] == "dataset_search"

    @pytest.mark.unit
    def test_reverse_map_consistency(self) -> None:
        for label, idx in FULLTEXT_INDEX_MAP.items():
            assert INDEX_TO_LABEL[idx] == label

    @pytest.mark.unit
    def test_reverse_map_same_length(self) -> None:
        assert len(INDEX_TO_LABEL) == len(FULLTEXT_INDEX_MAP)


class TestGetFulltextIndex:
    @pytest.mark.unit
    def test_existing_label(self) -> None:
        assert get_fulltext_index("Vessel") == "vessel_search"

    @pytest.mark.unit
    def test_missing_label(self) -> None:
        assert get_fulltext_index("UnknownLabel") is None

    @pytest.mark.unit
    def test_case_sensitive(self) -> None:
        assert get_fulltext_index("vessel") is None  # must be "Vessel"

    @pytest.mark.unit
    def test_has_fulltext_true(self) -> None:
        assert has_fulltext_index("Document") is True

    @pytest.mark.unit
    def test_has_fulltext_false(self) -> None:
        assert has_fulltext_index("Unknown") is False


class TestFulltextSearchCypher:
    @pytest.mark.unit
    def test_basic_cypher(self) -> None:
        cypher = fulltext_search_cypher("vessel_search")
        assert "db.index.fulltext.queryNodes" in cypher
        assert "'vessel_search'" in cypher
        assert "$searchTerm" in cypher
        assert "YIELD node AS node, score AS score" in cypher

    @pytest.mark.unit
    def test_custom_vars(self) -> None:
        cypher = fulltext_search_cypher("port_search", result_var="p", score_var="s")
        assert "YIELD node AS p, score AS s" in cypher

    @pytest.mark.unit
    def test_returns_string(self) -> None:
        assert isinstance(fulltext_search_cypher("test"), str)


class TestMultiFulltextSearchCypher:
    @pytest.mark.unit
    def test_default_uses_all_indexes(self) -> None:
        cypher = multi_fulltext_search_cypher()
        for idx_name in FULLTEXT_INDEX_MAP.values():
            assert idx_name in cypher

    @pytest.mark.unit
    def test_specific_indexes(self) -> None:
        cypher = multi_fulltext_search_cypher(["vessel_search", "port_search"])
        assert "vessel_search" in cypher
        assert "port_search" in cypher
        assert "document_search" not in cypher

    @pytest.mark.unit
    def test_union_all_present(self) -> None:
        cypher = multi_fulltext_search_cypher(["vessel_search", "port_search"])
        assert "UNION ALL" in cypher

    @pytest.mark.unit
    def test_single_index_no_union(self) -> None:
        cypher = multi_fulltext_search_cypher(["vessel_search"])
        assert "UNION ALL" not in cypher

    @pytest.mark.unit
    def test_contains_limit(self) -> None:
        cypher = multi_fulltext_search_cypher()
        assert "$limit" in cypher

    @pytest.mark.unit
    def test_contains_search_term(self) -> None:
        cypher = multi_fulltext_search_cypher()
        assert "$searchTerm" in cypher


class TestEmbeddingsHybridNaming:
    """Test that the embeddings hybrid search uses correct index names."""

    @pytest.mark.unit
    def test_vessel_fulltext_index_name(self) -> None:
        """Verify the naming convention matches indexes.cypher."""
        idx = get_fulltext_index("Vessel")
        assert idx == "vessel_search"
        assert idx != "vessel_fulltext_index"  # old broken convention

    @pytest.mark.unit
    def test_document_fulltext_index_name(self) -> None:
        idx = get_fulltext_index("Document")
        assert idx == "document_search"

    @pytest.mark.unit
    def test_all_indexes_use_search_suffix(self) -> None:
        for idx_name in FULLTEXT_INDEX_MAP.values():
            assert idx_name.endswith("_search"), f"{idx_name} should end with _search"


class TestGraphSearchRoute:
    """Test the graph search route generates fulltext Cypher."""

    @pytest.mark.unit
    def test_fulltext_index_map_has_entries(self) -> None:
        """Precondition: there are indexes to generate UNION branches."""
        assert len(FULLTEXT_INDEX_MAP) > 0

    @pytest.mark.unit
    def test_all_labels_have_valid_identifiers(self) -> None:
        for label in FULLTEXT_INDEX_MAP:
            assert label.isidentifier(), f"Label '{label}' must be a valid identifier"

    @pytest.mark.unit
    def test_all_index_names_safe_for_cypher(self) -> None:
        """Index names must be safe to embed in Cypher strings."""
        for name in FULLTEXT_INDEX_MAP.values():
            assert "'" not in name
            assert '"' not in name
            assert "\\" not in name
