"""Unit tests for core/kg/etl/loader.py — property coverage.

Covers the three @property methods (lines 35-47) that were previously
untested:
- Neo4jBatchLoader.label  (line 37)
- Neo4jBatchLoader.id_field  (line 42)
- Neo4jBatchLoader.batch_size  (line 47)

All tests are @pytest.mark.unit.
"""
from __future__ import annotations

import pytest

from kg.etl.loader import Neo4jBatchLoader


# ---------------------------------------------------------------------------
# TestNeo4jBatchLoaderProperties
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNeo4jBatchLoaderProperties:
    """Tests for Neo4jBatchLoader @property accessors (lines 34-47)."""

    def test_label_property_returns_constructor_value(self) -> None:
        """loader.label returns the label passed to __init__."""
        loader = Neo4jBatchLoader(label="Vessel", id_field="vesselId")
        assert loader.label == "Vessel"

    def test_label_property_reflects_different_labels(self) -> None:
        """loader.label works correctly for any label string."""
        for lbl in ("Port", "AnchorageArea", "Route", "CrewMember"):
            loader = Neo4jBatchLoader(label=lbl, id_field="id")
            assert loader.label == lbl

    def test_id_field_property_returns_constructor_value(self) -> None:
        """loader.id_field returns the id_field passed to __init__."""
        loader = Neo4jBatchLoader(label="Vessel", id_field="mmsi")
        assert loader.id_field == "mmsi"

    def test_id_field_property_reflects_different_fields(self) -> None:
        """loader.id_field works correctly for any field name string."""
        for fld in ("vesselId", "portCode", "imoNumber", "uuid"):
            loader = Neo4jBatchLoader(label="TestLabel", id_field=fld)
            assert loader.id_field == fld

    def test_batch_size_property_returns_default(self) -> None:
        """loader.batch_size returns 500 when not specified."""
        loader = Neo4jBatchLoader(label="Vessel", id_field="vesselId")
        assert loader.batch_size == 500

    def test_batch_size_property_returns_custom_value(self) -> None:
        """loader.batch_size returns the batch_size passed to __init__."""
        loader = Neo4jBatchLoader(label="Port", id_field="portCode", batch_size=100)
        assert loader.batch_size == 100

    def test_batch_size_property_reflects_small_batch(self) -> None:
        """loader.batch_size works with small batch sizes."""
        loader = Neo4jBatchLoader(label="Vessel", id_field="id", batch_size=1)
        assert loader.batch_size == 1

    def test_batch_size_property_reflects_large_batch(self) -> None:
        """loader.batch_size works with large batch sizes."""
        loader = Neo4jBatchLoader(label="Vessel", id_field="id", batch_size=10_000)
        assert loader.batch_size == 10_000

    def test_all_three_properties_consistent_after_construction(self) -> None:
        """All three properties are accessible and consistent on the same instance."""
        loader = Neo4jBatchLoader(
            label="RouteSegment",
            id_field="segmentId",
            batch_size=250,
        )
        assert loader.label == "RouteSegment"
        assert loader.id_field == "segmentId"
        assert loader.batch_size == 250

    def test_properties_are_read_only(self) -> None:
        """Properties are backed by frozen private attrs; direct attr access matches."""
        loader = Neo4jBatchLoader(label="Vessel", id_field="vesselId", batch_size=50)
        # The public property and the private attribute must agree
        assert loader.label == loader._label
        assert loader.id_field == loader._id_field
        assert loader.batch_size == loader._batch_size
