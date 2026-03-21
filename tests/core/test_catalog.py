"""Unit tests for kg.catalog package.

Covers QualityDimension, QualityScore, SchemaChange, CatalogEntry,
calculate_quality_score, and CatalogManager. All tests run without
any external dependencies or running services.
"""

from __future__ import annotations

import pytest

from kg.catalog import (
    CatalogEntry,
    CatalogManager,
    QualityDimension,
    SchemaChange,
    calculate_quality_score,
)
from kg.catalog.models import CatalogEntry, QualityDimension, QualityScore, SchemaChange
from kg.catalog.quality import calculate_quality_score
from kg.catalog.manager import CatalogManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(
    entry_id: str = "node.Vessel",
    name: str = "Vessel",
    entry_type: str = "NODE_LABEL",
    description: str = "",
    owner: str = "",
    tags: tuple[str, ...] = (),
    updated_at: str = "",
) -> CatalogEntry:
    return CatalogEntry(
        id=entry_id,
        name=name,
        entry_type=entry_type,
        description=description,
        owner=owner,
        tags=tags,
        updated_at=updated_at,
    )


# ===========================================================================
# QualityDimension
# ===========================================================================


@pytest.mark.unit
class TestQualityDimension:
    """QualityDimension enum structure."""

    def test_four_dimensions(self) -> None:
        members = list(QualityDimension)
        assert len(members) == 4

    def test_str_enum(self) -> None:
        assert isinstance(QualityDimension.COMPLETENESS, str)

    def test_member_values(self) -> None:
        assert QualityDimension.COMPLETENESS == "completeness"
        assert QualityDimension.ACCURACY == "accuracy"
        assert QualityDimension.FRESHNESS == "freshness"
        assert QualityDimension.CONSISTENCY == "consistency"

    def test_usable_as_string(self) -> None:
        dim = QualityDimension.FRESHNESS
        assert f"dim={dim}" == "dim=freshness"


# ===========================================================================
# QualityScore
# ===========================================================================


@pytest.mark.unit
class TestQualityScore:
    """QualityScore frozen dataclass."""

    def test_frozen(self) -> None:
        qs = QualityScore(dimension=QualityDimension.ACCURACY, score=0.9)
        with pytest.raises((AttributeError, TypeError)):
            qs.score = 0.5  # type: ignore[misc]

    def test_valid_score(self) -> None:
        qs = QualityScore(
            dimension=QualityDimension.COMPLETENESS,
            score=0.75,
            details="3/4 fields populated",
        )
        assert qs.dimension == QualityDimension.COMPLETENESS
        assert qs.score == 0.75
        assert "3/4" in qs.details

    def test_default_details_empty(self) -> None:
        qs = QualityScore(dimension=QualityDimension.FRESHNESS, score=1.0)
        assert qs.details == ""

    def test_score_zero_allowed(self) -> None:
        qs = QualityScore(dimension=QualityDimension.CONSISTENCY, score=0.0)
        assert qs.score == 0.0


# ===========================================================================
# SchemaChange
# ===========================================================================


@pytest.mark.unit
class TestSchemaChange:
    """SchemaChange frozen dataclass."""

    def test_frozen(self) -> None:
        sc = SchemaChange(
            version="1.0.0",
            timestamp="2026-01-01T00:00:00",
            change_type="ADD_LABEL",
            target="Vessel",
        )
        with pytest.raises((AttributeError, TypeError)):
            sc.version = "2.0.0"  # type: ignore[misc]

    def test_fields(self) -> None:
        sc = SchemaChange(
            version="1.2.0",
            timestamp="2026-03-01T12:00:00",
            change_type="ADD_PROPERTY",
            target="Vessel.mmsi",
        )
        assert sc.version == "1.2.0"
        assert sc.timestamp == "2026-03-01T12:00:00"
        assert sc.change_type == "ADD_PROPERTY"
        assert sc.target == "Vessel.mmsi"

    def test_optional_defaults(self) -> None:
        sc = SchemaChange(
            version="0.1.0",
            timestamp="2026-01-01T00:00:00",
            change_type="REMOVE_LABEL",
            target="OldLabel",
        )
        assert sc.description == ""
        assert sc.author == ""

    def test_with_optional_fields(self) -> None:
        sc = SchemaChange(
            version="2.0.0",
            timestamp="2026-06-01T08:00:00",
            change_type="MODIFY_PROPERTY",
            target="Port.code",
            description="Renamed from portCode",
            author="dev-team",
        )
        assert sc.description == "Renamed from portCode"
        assert sc.author == "dev-team"


# ===========================================================================
# CatalogEntry
# ===========================================================================


@pytest.mark.unit
class TestCatalogEntry:
    """CatalogEntry frozen dataclass and derived properties."""

    def test_defaults(self) -> None:
        entry = CatalogEntry(id="x", name="X", entry_type="NODE_LABEL")
        assert entry.description == ""
        assert entry.owner == ""
        assert entry.tags == ()
        assert entry.quality_scores == ()
        assert entry.schema_history == ()
        assert entry.properties == ()
        assert entry.created_at == ""
        assert entry.updated_at == ""

    def test_overall_quality_empty(self) -> None:
        entry = _make_entry()
        assert entry.overall_quality == 0.0

    def test_overall_quality_average(self) -> None:
        scores = (
            QualityScore(dimension=QualityDimension.COMPLETENESS, score=0.6),
            QualityScore(dimension=QualityDimension.ACCURACY, score=1.0),
            QualityScore(dimension=QualityDimension.FRESHNESS, score=0.8),
            QualityScore(dimension=QualityDimension.CONSISTENCY, score=1.0),
        )
        entry = CatalogEntry(
            id="node.Vessel",
            name="Vessel",
            entry_type="NODE_LABEL",
            quality_scores=scores,
        )
        expected = (0.6 + 1.0 + 0.8 + 1.0) / 4
        assert abs(entry.overall_quality - expected) < 1e-9

    def test_frozen(self) -> None:
        entry = _make_entry()
        with pytest.raises((AttributeError, TypeError)):
            entry.name = "Other"  # type: ignore[misc]

    def test_single_quality_score(self) -> None:
        score = QualityScore(dimension=QualityDimension.ACCURACY, score=0.5)
        entry = CatalogEntry(
            id="idx.x",
            name="X",
            entry_type="INDEX",
            quality_scores=(score,),
        )
        assert entry.overall_quality == 0.5


# ===========================================================================
# calculate_quality_score
# ===========================================================================


@pytest.mark.unit
class TestCalculateQualityScore:
    """Heuristic quality scorer across all four dimensions."""

    def test_returns_4_scores(self) -> None:
        entry = _make_entry()
        scores = calculate_quality_score(entry)
        assert len(scores) == 4

    def test_dimensions_all_present(self) -> None:
        entry = _make_entry()
        scores = calculate_quality_score(entry)
        dims = {s.dimension for s in scores}
        assert dims == set(QualityDimension)

    def test_completeness_full(self) -> None:
        entry = _make_entry(
            description="Tracks maritime vessels",
            owner="maritime-team",
            tags=("vessel", "maritime"),
        )
        scores = calculate_quality_score(entry)
        comp = next(s for s in scores if s.dimension == QualityDimension.COMPLETENESS)
        assert comp.score == 1.0

    def test_completeness_empty(self) -> None:
        entry = _make_entry(description="", owner="", tags=())
        scores = calculate_quality_score(entry)
        comp = next(s for s in scores if s.dimension == QualityDimension.COMPLETENESS)
        assert comp.score == 0.0

    def test_freshness_recent(self) -> None:
        # Use a date within the last 30 days
        entry = _make_entry(updated_at="2026-03-15T12:00:00")
        scores = calculate_quality_score(entry)
        fresh = next(s for s in scores if s.dimension == QualityDimension.FRESHNESS)
        assert fresh.score == 1.0

    def test_freshness_missing_updated_at(self) -> None:
        entry = _make_entry(updated_at="")
        scores = calculate_quality_score(entry)
        fresh = next(s for s in scores if s.dimension == QualityDimension.FRESHNESS)
        assert fresh.score == 0.0

    def test_consistency_valid_type(self) -> None:
        entry = _make_entry(entry_type="NODE_LABEL")
        scores = calculate_quality_score(entry)
        cons = next(s for s in scores if s.dimension == QualityDimension.CONSISTENCY)
        assert cons.score == 1.0

    def test_consistency_invalid_type(self) -> None:
        entry = _make_entry(entry_type="UNKNOWN_TYPE")
        scores = calculate_quality_score(entry)
        cons = next(s for s in scores if s.dimension == QualityDimension.CONSISTENCY)
        assert cons.score == 0.0

    def test_accuracy_placeholder_is_1(self) -> None:
        entry = _make_entry()
        scores = calculate_quality_score(entry)
        acc = next(s for s in scores if s.dimension == QualityDimension.ACCURACY)
        assert acc.score == 1.0

    def test_scores_in_range(self) -> None:
        entry = _make_entry(
            description="A port node",
            owner="ops-team",
            tags=("port",),
            updated_at="2026-03-01T00:00:00",
        )
        scores = calculate_quality_score(entry)
        for s in scores:
            assert 0.0 <= s.score <= 1.0


# ===========================================================================
# CatalogManager
# ===========================================================================


@pytest.mark.unit
class TestCatalogManager:
    """CatalogManager CRUD and mutation helpers."""

    def test_register_and_get(self) -> None:
        mgr = CatalogManager()
        entry = _make_entry()
        mgr.register(entry)
        retrieved = mgr.get("node.Vessel")
        assert retrieved is not None
        assert retrieved.id == "node.Vessel"

    def test_get_nonexistent_returns_none(self) -> None:
        mgr = CatalogManager()
        assert mgr.get("does.not.exist") is None

    def test_list_all_sorted(self) -> None:
        mgr = CatalogManager()
        mgr.register(_make_entry("rel.DOCKED_AT", "DOCKED_AT", "RELATIONSHIP_TYPE"))
        mgr.register(_make_entry("node.Vessel", "Vessel", "NODE_LABEL"))
        mgr.register(_make_entry("node.Port", "Port", "NODE_LABEL"))
        names = [e.name for e in mgr.list_all()]
        assert names == sorted(names, key=str.lower)

    def test_list_by_type(self) -> None:
        mgr = CatalogManager()
        mgr.register(_make_entry("node.Vessel", "Vessel", "NODE_LABEL"))
        mgr.register(_make_entry("node.Port", "Port", "NODE_LABEL"))
        mgr.register(_make_entry("rel.DOCKED_AT", "DOCKED_AT", "RELATIONSHIP_TYPE"))
        node_entries = mgr.list_by_type("NODE_LABEL")
        assert len(node_entries) == 2
        for e in node_entries:
            assert e.entry_type == "NODE_LABEL"

    def test_search_by_name(self) -> None:
        mgr = CatalogManager()
        mgr.register(_make_entry("node.Vessel", "Vessel", "NODE_LABEL"))
        mgr.register(_make_entry("node.Port", "Port", "NODE_LABEL"))
        results = mgr.search("vessel")
        assert len(results) == 1
        assert results[0].name == "Vessel"

    def test_search_case_insensitive(self) -> None:
        mgr = CatalogManager()
        mgr.register(_make_entry("node.Vessel", "Vessel", "NODE_LABEL"))
        results = mgr.search("VESSEL")
        assert len(results) == 1

    def test_search_by_description(self) -> None:
        mgr = CatalogManager()
        mgr.register(_make_entry("node.Port", "Port", "NODE_LABEL", description="Maritime harbour"))
        results = mgr.search("harbour")
        assert len(results) == 1

    def test_remove(self) -> None:
        mgr = CatalogManager()
        mgr.register(_make_entry())
        removed = mgr.remove("node.Vessel")
        assert removed is True
        assert mgr.get("node.Vessel") is None

    def test_remove_nonexistent(self) -> None:
        mgr = CatalogManager()
        result = mgr.remove("no.such.entry")
        assert result is False

    def test_update_quality(self) -> None:
        mgr = CatalogManager()
        mgr.register(_make_entry())
        new_scores = [
            QualityScore(dimension=QualityDimension.COMPLETENESS, score=0.8),
        ]
        updated = mgr.update_quality("node.Vessel", new_scores)
        assert updated is not None
        assert len(updated.quality_scores) == 1
        assert updated.quality_scores[0].score == 0.8
        # Ensure registry is updated
        stored = mgr.get("node.Vessel")
        assert stored is not None
        assert stored.quality_scores[0].score == 0.8

    def test_update_quality_nonexistent(self) -> None:
        mgr = CatalogManager()
        result = mgr.update_quality("missing", [])
        assert result is None

    def test_add_schema_change(self) -> None:
        mgr = CatalogManager()
        mgr.register(_make_entry())
        change = SchemaChange(
            version="1.1.0",
            timestamp="2026-03-01T00:00:00",
            change_type="ADD_PROPERTY",
            target="Vessel.imo",
        )
        updated = mgr.add_schema_change("node.Vessel", change)
        assert updated is not None
        assert len(updated.schema_history) == 1
        assert updated.schema_history[0].version == "1.1.0"

    def test_add_schema_change_appends(self) -> None:
        mgr = CatalogManager()
        initial_change = SchemaChange(
            version="1.0.0",
            timestamp="2026-01-01T00:00:00",
            change_type="ADD_LABEL",
            target="Vessel",
        )
        entry = CatalogEntry(
            id="node.Vessel",
            name="Vessel",
            entry_type="NODE_LABEL",
            schema_history=(initial_change,),
        )
        mgr.register(entry)
        new_change = SchemaChange(
            version="1.1.0",
            timestamp="2026-02-01T00:00:00",
            change_type="ADD_PROPERTY",
            target="Vessel.mmsi",
        )
        updated = mgr.add_schema_change("node.Vessel", new_change)
        assert updated is not None
        assert len(updated.schema_history) == 2

    def test_refresh_quality(self) -> None:
        mgr = CatalogManager()
        entry = _make_entry(
            description="Vessel asset",
            owner="team-a",
            tags=("maritime",),
            updated_at="2026-03-15T00:00:00",
        )
        mgr.register(entry)
        updated = mgr.refresh_quality("node.Vessel")
        assert updated is not None
        assert len(updated.quality_scores) == 4

    def test_refresh_quality_nonexistent(self) -> None:
        mgr = CatalogManager()
        result = mgr.refresh_quality("ghost.entry")
        assert result is None

    def test_register_overwrite(self) -> None:
        mgr = CatalogManager()
        entry1 = _make_entry(description="First")
        entry2 = CatalogEntry(
            id="node.Vessel",
            name="Vessel",
            entry_type="NODE_LABEL",
            description="Second",
        )
        mgr.register(entry1)
        mgr.register(entry2)
        stored = mgr.get("node.Vessel")
        assert stored is not None
        assert stored.description == "Second"
