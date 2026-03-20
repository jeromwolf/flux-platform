"""Unit tests for Korean maritime terminology dictionary."""

from __future__ import annotations

import pytest

from kg.nlp.maritime_terms import (
    ENTITY_SYNONYMS,
    NAMED_ENTITIES,
    PROPERTY_VALUE_MAP,
    RELATIONSHIP_KEYWORDS,
    get_term_context_for_llm,
    resolve_entity,
    resolve_named_entity,
    resolve_property_value,
)


@pytest.mark.unit
class TestEntitySynonyms:
    """Test ENTITY_SYNONYMS dictionary."""

    def test_dict_is_non_empty(self):
        """Dictionary should contain multiple entries."""
        assert len(ENTITY_SYNONYMS) > 0
        assert len(ENTITY_SYNONYMS) >= 100  # Should have at least 100 mappings

    def test_vessel_maps_to_vessel(self):
        """선박 should map to Vessel."""
        assert ENTITY_SYNONYMS["선박"] == "Vessel"

    def test_port_maps_to_port(self):
        """항구 should map to Port."""
        assert ENTITY_SYNONYMS["항구"] == "Port"

    def test_tanker_maps_to_tanker(self):
        """유조선 should map to Tanker."""
        assert ENTITY_SYNONYMS["유조선"] == "Tanker"

    def test_all_values_are_valid_neo4j_labels(self):
        """All values should be valid Neo4j labels (PascalCase, no spaces)."""
        for _korean_term, label in ENTITY_SYNONYMS.items():
            # Check that label starts with uppercase
            assert label[0].isupper(), f"Label '{label}' should start with uppercase"
            # Check that label contains no spaces
            assert " " not in label, f"Label '{label}' should not contain spaces"
            # Check that label is PascalCase or SCREAMING_SNAKE_CASE
            # Allow PascalCase (e.g., "Vessel") and acronyms (e.g., "AIS", "EEZ")
            assert label.replace("_", "").isalnum(), f"Label '{label}' should be alphanumeric"


@pytest.mark.unit
class TestRelationshipKeywords:
    """Test RELATIONSHIP_KEYWORDS dictionary."""

    def test_dict_is_non_empty(self):
        """Dictionary should contain multiple entries."""
        assert len(RELATIONSHIP_KEYWORDS) > 0
        assert len(RELATIONSHIP_KEYWORDS) >= 20  # Should have at least 20 mappings

    def test_contains_expected_keywords(self):
        """Dictionary should contain expected location and voyage keywords."""
        assert "위치한" in RELATIONSHIP_KEYWORDS
        assert RELATIONSHIP_KEYWORDS["위치한"] == "LOCATED_AT"

        assert "항해중인" in RELATIONSHIP_KEYWORDS
        assert RELATIONSHIP_KEYWORDS["항해중인"] == "ON_VOYAGE"

    def test_values_are_valid_relationship_types(self):
        """All values should be valid relationship types (SCREAMING_SNAKE_CASE)."""
        for _korean_phrase, rel_type in RELATIONSHIP_KEYWORDS.items():
            # Check that relationship type is uppercase with underscores
            assert rel_type.isupper(), f"Relationship '{rel_type}' should be uppercase"
            # Allow uppercase letters and underscores only
            assert all(c.isupper() or c == "_" for c in rel_type), (
                f"Relationship '{rel_type}' should use SCREAMING_SNAKE_CASE"
            )


@pytest.mark.unit
class TestPropertyValueMap:
    """Test PROPERTY_VALUE_MAP dictionary."""

    def test_dict_is_non_empty(self):
        """Dictionary should contain multiple property mappings."""
        assert len(PROPERTY_VALUE_MAP) > 0
        assert len(PROPERTY_VALUE_MAP) >= 5  # At least 5 property types

    def test_vesseltype_key_exists(self):
        """vesselType key should exist."""
        assert "vesselType" in PROPERTY_VALUE_MAP

    def test_vesseltype_has_container_ship_mapping(self):
        """vesselType should map 컨테이너선 to ContainerShip."""
        assert "컨테이너선" in PROPERTY_VALUE_MAP["vesselType"]
        assert PROPERTY_VALUE_MAP["vesselType"]["컨테이너선"] == "ContainerShip"


@pytest.mark.unit
class TestNamedEntities:
    """Test NAMED_ENTITIES dictionary."""

    def test_dict_is_non_empty(self):
        """Dictionary should contain named entity mappings."""
        assert len(NAMED_ENTITIES) > 0
        assert len(NAMED_ENTITIES) >= 10  # At least 10 named entities

    def test_busan_port_returns_dict_with_label_key_value(self):
        """부산항 should return dict with label, key, value."""
        busan = NAMED_ENTITIES["부산항"]
        assert isinstance(busan, dict)
        assert "label" in busan
        assert "key" in busan
        assert "value" in busan
        assert busan["label"] == "Port"
        assert busan["key"] == "unlocode"
        assert busan["value"] == "KRPUS"

    def test_unknown_name_not_in_dict(self):
        """Unknown name should not be in dictionary."""
        assert "존재하지않는항구" not in NAMED_ENTITIES


@pytest.mark.unit
class TestResolveEntity:
    """Test resolve_entity function."""

    def test_exact_match_returns_label(self):
        """Exact match should return the correct label."""
        assert resolve_entity("선박") == "Vessel"
        assert resolve_entity("항구") == "Port"
        assert resolve_entity("유조선") == "Tanker"

    def test_partial_match_returns_label(self):
        """Partial match should return label (e.g., '대형선박' contains '선박')."""
        # Test partial match where dictionary key is in query term
        result = resolve_entity("대형선박")
        assert result == "Vessel"  # "선박" is in "대형선박"

    def test_unknown_term_returns_none(self):
        """Unknown term should return None."""
        assert resolve_entity("알수없는용어") is None
        assert resolve_entity("존재하지않음") is None

    def test_empty_string_returns_label_due_to_partial_match(self):
        """Empty string matches all keys via partial match, returns a label."""
        # The implementation does partial matching, so empty string will match
        result = resolve_entity("")
        # Should return some label (not None) due to partial match logic
        assert result is not None
        assert isinstance(result, str)


@pytest.mark.unit
class TestResolvePropertyValue:
    """Test resolve_property_value function."""

    def test_known_property_and_value_returns_english(self):
        """Known property and value should return English translation."""
        result = resolve_property_value("vesselType", "컨테이너선")
        assert result == "ContainerShip"

        result = resolve_property_value("currentStatus", "항해중")
        assert result == "UNDERWAY"

    def test_unknown_property_returns_none(self):
        """Unknown property should return None."""
        result = resolve_property_value("unknownProperty", "some_value")
        assert result is None

    def test_unknown_value_returns_none(self):
        """Unknown value for known property should return None."""
        result = resolve_property_value("vesselType", "알수없는선박")
        assert result is None


@pytest.mark.unit
class TestResolveNamedEntity:
    """Test resolve_named_entity function."""

    def test_known_name_returns_dict(self):
        """Known name should return dict with label, key, value."""
        result = resolve_named_entity("부산항")
        assert result is not None
        assert isinstance(result, dict)
        assert result["label"] == "Port"
        assert result["key"] == "unlocode"
        assert result["value"] == "KRPUS"

    def test_unknown_name_returns_none(self):
        """Unknown name should return None."""
        result = resolve_named_entity("존재하지않는곳")
        assert result is None

    def test_returned_dict_has_label_key(self):
        """Returned dict should have 'label' key."""
        result = resolve_named_entity("KRISO")
        assert result is not None
        assert "label" in result
        assert result["label"] == "Organization"


@pytest.mark.unit
class TestGetTermContextForLLM:
    """Test get_term_context_for_llm function."""

    def test_returns_non_empty_string(self):
        """Function should return a non-empty string."""
        result = get_term_context_for_llm()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_korean_maritime_terms_reference(self):
        """Output should contain the header 'Korean Maritime Terms Reference'."""
        result = get_term_context_for_llm()
        assert "Korean Maritime Terms Reference" in result

    def test_contains_entity_labels_section(self):
        """Output should contain 'Entity Labels:' section."""
        result = get_term_context_for_llm()
        assert "Entity Labels:" in result

    def test_contains_property_values_section(self):
        """Output should contain 'Property Values:' section."""
        result = get_term_context_for_llm()
        assert "Property Values:" in result

    def test_output_is_well_formatted(self):
        """Output should be well-formatted with newlines and indentation."""
        result = get_term_context_for_llm()
        lines = result.split("\n")
        # Should have multiple lines
        assert len(lines) > 5
        # Should have indented lines (starting with spaces)
        assert any(line.startswith("  ") for line in lines)

    def test_includes_sample_entity_mappings(self):
        """Output should include some entity mappings."""
        result = get_term_context_for_llm()
        # Should mention some entity labels
        assert "Vessel" in result or "Port" in result

    def test_includes_sample_property_mappings(self):
        """Output should include some property value mappings."""
        result = get_term_context_for_llm()
        # Should mention vesselType property
        assert "vesselType" in result
