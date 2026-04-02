"""Unit tests for domains/maritime/s100/s100_mapping.py.

Covers:
- S100MappingEntry frozen dataclass construction and immutability
- to_kg_properties with present/absent keys
- S100ToKGMapper default registration (6 S-101 mappings)
- register and lookup by product + feature type
- list_mappings with and without product filter
- mapping_count property
- S100_PRODUCTS dict has 6 entries
- S100FeatureMapping Protocol isinstance check
"""

from __future__ import annotations

import pytest

from maritime.s100.s100_mapping import (
    S100FeatureMapping,
    S100MappingEntry,
    S100ToKGMapper,
    S100_PRODUCTS,
    S101_MAPPINGS,
)


# ---------------------------------------------------------------------------
# S100MappingEntry tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestS100MappingEntry:
    def test_basic_construction(self):
        entry = S100MappingEntry(
            s100_product="S-101",
            feature_type="DepthArea",
            kg_label="SeaArea",
        )
        assert entry.s100_product == "S-101"
        assert entry.feature_type == "DepthArea"
        assert entry.kg_label == "SeaArea"

    def test_default_optional_fields(self):
        entry = S100MappingEntry(
            s100_product="S-102",
            feature_type="BathymetricContour",
            kg_label="Contour",
        )
        assert entry.property_map == {}
        assert entry.relationship_type == ""
        assert entry.relationship_target == ""

    def test_frozen_immutability(self):
        entry = S100MappingEntry(
            s100_product="S-101",
            feature_type="Harbour",
            kg_label="Port",
        )
        with pytest.raises((AttributeError, TypeError)):
            entry.kg_label = "NewLabel"  # type: ignore[misc]

    def test_to_kg_properties_all_present(self):
        entry = S100MappingEntry(
            s100_product="S-101",
            feature_type="Harbour",
            kg_label="Port",
            property_map={
                "featureName": "name",
                "unloCode": "unlocode",
                "countryName": "country",
            },
        )
        attrs = {"featureName": "Busan Port", "unloCode": "KRPUS", "countryName": "South Korea"}
        result = entry.to_kg_properties(attrs)
        assert result == {"name": "Busan Port", "unlocode": "KRPUS", "country": "South Korea"}

    def test_to_kg_properties_partial_present(self):
        entry = S100MappingEntry(
            s100_product="S-101",
            feature_type="Harbour",
            kg_label="Port",
            property_map={
                "featureName": "name",
                "unloCode": "unlocode",
            },
        )
        attrs = {"featureName": "Incheon"}
        result = entry.to_kg_properties(attrs)
        assert result == {"name": "Incheon"}
        assert "unlocode" not in result

    def test_to_kg_properties_empty_attrs(self):
        entry = S100MappingEntry(
            s100_product="S-101",
            feature_type="Fairway",
            kg_label="Channel",
            property_map={"featureName": "name"},
        )
        result = entry.to_kg_properties({})
        assert result == {}

    def test_to_kg_properties_no_property_map(self):
        entry = S100MappingEntry(
            s100_product="S-101",
            feature_type="AnchorageArea",
            kg_label="Anchorage",
        )
        result = entry.to_kg_properties({"featureName": "Anchorage 1"})
        assert result == {}

    def test_with_relationship_fields(self):
        entry = S100MappingEntry(
            s100_product="S-101",
            feature_type="TrafficSeparationScheme",
            kg_label="TSS",
            relationship_type="LOCATED_IN",
            relationship_target="SeaArea",
        )
        assert entry.relationship_type == "LOCATED_IN"
        assert entry.relationship_target == "SeaArea"


# ---------------------------------------------------------------------------
# S100_PRODUCTS dict tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestS100Products:
    def test_has_six_entries(self):
        assert len(S100_PRODUCTS) == 6

    def test_required_products_present(self):
        for product in ("S-101", "S-102", "S-104", "S-111", "S-124", "S-421"):
            assert product in S100_PRODUCTS

    def test_s101_description(self):
        assert "ENC" in S100_PRODUCTS["S-101"] or "Navigational" in S100_PRODUCTS["S-101"]


# ---------------------------------------------------------------------------
# S101_MAPPINGS list tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestS101Mappings:
    def test_has_six_entries(self):
        assert len(S101_MAPPINGS) == 6

    def test_all_are_s101(self):
        for entry in S101_MAPPINGS:
            assert entry.s100_product == "S-101"

    def test_feature_types_unique(self):
        types = [e.feature_type for e in S101_MAPPINGS]
        assert len(types) == len(set(types))


# ---------------------------------------------------------------------------
# S100ToKGMapper tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestS100ToKGMapper:
    def test_default_mapping_count(self):
        mapper = S100ToKGMapper()
        assert mapper.mapping_count == 6

    def test_lookup_existing(self):
        mapper = S100ToKGMapper()
        entry = mapper.lookup("S-101", "DepthArea")
        assert entry is not None
        assert entry.kg_label == "SeaArea"

    def test_lookup_nonexistent_returns_none(self):
        mapper = S100ToKGMapper()
        result = mapper.lookup("S-999", "NonExistent")
        assert result is None

    def test_lookup_wrong_product_returns_none(self):
        mapper = S100ToKGMapper()
        result = mapper.lookup("S-102", "DepthArea")
        assert result is None

    def test_register_new_mapping(self):
        mapper = S100ToKGMapper()
        new_entry = S100MappingEntry(
            s100_product="S-111",
            feature_type="SurfaceCurrent",
            kg_label="Current",
            property_map={"speed": "speed", "direction": "direction"},
        )
        mapper.register(new_entry)
        assert mapper.mapping_count == 7
        result = mapper.lookup("S-111", "SurfaceCurrent")
        assert result is not None
        assert result.kg_label == "Current"

    def test_register_overwrites_existing(self):
        mapper = S100ToKGMapper()
        override = S100MappingEntry(
            s100_product="S-101",
            feature_type="DepthArea",
            kg_label="OverriddenLabel",
        )
        mapper.register(override)
        # Count stays the same since key is overwritten
        assert mapper.mapping_count == 6
        result = mapper.lookup("S-101", "DepthArea")
        assert result is not None
        assert result.kg_label == "OverriddenLabel"

    def test_list_mappings_all(self):
        mapper = S100ToKGMapper()
        all_mappings = mapper.list_mappings()
        assert len(all_mappings) == 6

    def test_list_mappings_by_product_s101(self):
        mapper = S100ToKGMapper()
        s101 = mapper.list_mappings("S-101")
        assert len(s101) == 6
        for m in s101:
            assert m.s100_product == "S-101"

    def test_list_mappings_by_unknown_product(self):
        mapper = S100ToKGMapper()
        result = mapper.list_mappings("S-999")
        assert result == []

    def test_list_mappings_after_register_other_product(self):
        mapper = S100ToKGMapper()
        new_entry = S100MappingEntry(
            s100_product="S-124",
            feature_type="NavigationalWarning",
            kg_label="Warning",
        )
        mapper.register(new_entry)
        s124 = mapper.list_mappings("S-124")
        assert len(s124) == 1
        assert s124[0].feature_type == "NavigationalWarning"
        # S-101 count unchanged
        assert len(mapper.list_mappings("S-101")) == 6

    def test_harbour_lookup_and_properties(self):
        mapper = S100ToKGMapper()
        entry = mapper.lookup("S-101", "Harbour")
        assert entry is not None
        result = entry.to_kg_properties({"featureName": "Busan", "unloCode": "KRPUS"})
        assert result["name"] == "Busan"
        assert result["unlocode"] == "KRPUS"


# ---------------------------------------------------------------------------
# S100FeatureMapping Protocol tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestS100FeatureMappingProtocol:
    def test_mapping_entry_satisfies_protocol(self):
        entry = S100MappingEntry(
            s100_product="S-101",
            feature_type="Fairway",
            kg_label="Channel",
        )
        assert isinstance(entry, S100FeatureMapping)

    def test_plain_object_without_protocol_attrs_fails(self):
        class _NotAMapping:
            pass

        assert not isinstance(_NotAMapping(), S100FeatureMapping)
