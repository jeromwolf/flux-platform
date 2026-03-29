"""Extended unit tests for online ConsistencyCheck implementations.

TC-CE01 ~ TC-CE07: Covers PropertyTypeCheck, RequiredPropertyCheck,
EnumValueCheck, CardinalityCheck, OrphanNodeCheck, DanglingRelationshipCheck
with mocked Neo4j sessions — no live connection required.
"""

from __future__ import annotations

from typing import Any

import pytest

from kg.consistency.checks import (
    CardinalityCheck,
    DanglingRelationshipCheck,
    EnumValueCheck,
    LabelSchema,
    OrphanNodeCheck,
    PropertySchema,
    PropertyTypeCheck,
    RequiredPropertyCheck,
    SchemaDefinition,
)
from kg.quality_gate import CheckStatus


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


class MockRecord:
    """Minimal dict-like record that supports key-based access."""

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)


class MockResult:
    """Minimal iterable result that also supports .single()."""

    def __init__(self, records: list[dict[str, Any]]) -> None:
        self._records = [MockRecord(r) for r in records]

    def single(self) -> MockRecord | None:
        return self._records[0] if self._records else None

    def __iter__(self):
        return iter(self._records)


class MockSession:
    """Configurable mock Neo4j session.

    Pass either:
    - a list/dict of results keyed by call index or Cypher substring, or
    - a callable ``(cypher, kwargs) -> MockResult``
    """

    def __init__(self, result_factory=None) -> None:
        self._factory = result_factory
        self._calls: list[tuple[str, dict]] = []

    def run(self, cypher: str, **kwargs) -> MockResult:
        self._calls.append((cypher, kwargs))
        if callable(self._factory):
            return self._factory(cypher, kwargs)
        # Default: return bad_count/missing_count = 0
        return MockResult([{"bad_count": 0, "missing_count": 0}])

    @property
    def call_count(self) -> int:
        return len(self._calls)


def _error_session(exc: Exception) -> MockSession:
    """Session that always raises the given exception."""

    def _raise(cypher, kwargs):
        raise exc

    return MockSession(result_factory=_raise)


# ---------------------------------------------------------------------------
# Common schema helpers
# ---------------------------------------------------------------------------


def _simple_schema() -> SchemaDefinition:
    return SchemaDefinition(
        labels={
            "Vessel": LabelSchema(
                properties={
                    "mmsi": PropertySchema(expected_type="str"),
                    "vesselType": PropertySchema(
                        expected_type="str",
                        enum_values=frozenset({"CARGO", "TANKER"}),
                    ),
                },
                required_properties=frozenset({"mmsi"}),
            ),
        },
        relationship_types=frozenset({"DOCKED_AT"}),
    )


def _empty_schema() -> SchemaDefinition:
    return SchemaDefinition()


# =============================================================================
# TC-CE01: PropertyTypeCheck
# =============================================================================


@pytest.mark.unit
class TestPropertyTypeCheckOnline:
    """PropertyTypeCheck with mocked session."""

    def test_session_none_skipped(self) -> None:
        """session=None → SKIPPED."""
        result = PropertyTypeCheck().check(_simple_schema(), session=None)
        assert result.status == CheckStatus.SKIPPED
        assert "reason" in result.details

    def test_clean_data_passes(self) -> None:
        """All properties match types → PASSED."""
        session = MockSession()  # always returns bad_count=0
        result = PropertyTypeCheck().check(_simple_schema(), session=session)
        assert result.status == CheckStatus.PASSED
        assert session.call_count == 2  # mmsi + vesselType

    def test_violations_found_fails(self) -> None:
        """bad_count > 0 on first property → FAILED with violation details."""
        call_index = [0]

        def factory(cypher: str, kwargs: dict) -> MockResult:
            # First call returns a violation, subsequent calls are clean.
            count = 3 if call_index[0] == 0 else 0
            call_index[0] += 1
            return MockResult([{"bad_count": count}])

        session = MockSession(result_factory=factory)
        result = PropertyTypeCheck().check(_simple_schema(), session=session)
        assert result.status == CheckStatus.FAILED
        assert "violations" in result.details
        assert len(result.details["violations"]) == 1
        assert result.details["violations"][0]["bad_count"] == 3

    def test_multiple_violations_fails(self) -> None:
        """All properties return bad_count=2 → FAILED, 2 violations."""
        session = MockSession(result_factory=lambda c, k: MockResult([{"bad_count": 2}]))
        result = PropertyTypeCheck().check(_simple_schema(), session=session)
        assert result.status == CheckStatus.FAILED
        assert len(result.details["violations"]) == 2

    def test_exception_during_query_fails(self) -> None:
        """RuntimeError during session.run → FAILED with error detail."""
        session = _error_session(RuntimeError("apoc not available"))
        result = PropertyTypeCheck().check(_simple_schema(), session=session)
        assert result.status == CheckStatus.FAILED
        assert "error" in result.details

    def test_unknown_expected_type_skipped_per_property(self) -> None:
        """Unknown expected_type is logged and skipped (no crash, still PASSED)."""
        schema = SchemaDefinition(
            labels={
                "Thing": LabelSchema(
                    properties={
                        "data": PropertySchema(expected_type="blob"),  # not in predicates
                    }
                )
            }
        )
        session = MockSession()
        result = PropertyTypeCheck().check(schema, session=session)
        # No queries should have been run for unknown type
        assert session.call_count == 0
        assert result.status == CheckStatus.PASSED

    def test_empty_schema_passes(self) -> None:
        """Empty schema → PASSED (0 pairs to check)."""
        session = MockSession()
        result = PropertyTypeCheck().check(_empty_schema(), session=session)
        assert result.status == CheckStatus.PASSED
        assert session.call_count == 0

    def test_passed_details_contain_checked_pairs(self) -> None:
        """PASSED result details include 'checked_pairs' count."""
        session = MockSession()
        result = PropertyTypeCheck().check(_simple_schema(), session=session)
        assert result.status == CheckStatus.PASSED
        assert "checked_pairs" in result.details
        assert result.details["checked_pairs"] == 2

    def test_no_record_returned_treated_as_zero(self) -> None:
        """session.run returns empty result (no records) → treated as bad_count=0."""
        session = MockSession(result_factory=lambda c, k: MockResult([]))
        result = PropertyTypeCheck().check(_simple_schema(), session=session)
        assert result.status == CheckStatus.PASSED


# =============================================================================
# TC-CE02: RequiredPropertyCheck
# =============================================================================


@pytest.mark.unit
class TestRequiredPropertyCheckOnline:
    """RequiredPropertyCheck with mocked session."""

    def test_session_none_skipped(self) -> None:
        """session=None → SKIPPED."""
        result = RequiredPropertyCheck().check(_simple_schema(), session=None)
        assert result.status == CheckStatus.SKIPPED

    def test_all_present_passes(self) -> None:
        """missing_count=0 → PASSED."""
        session = MockSession(result_factory=lambda c, k: MockResult([{"missing_count": 0}]))
        result = RequiredPropertyCheck().check(_simple_schema(), session=session)
        assert result.status == CheckStatus.PASSED
        # One required property: mmsi
        assert session.call_count == 1

    def test_missing_nodes_fails(self) -> None:
        """missing_count=5 → FAILED with missing_entries."""
        session = MockSession(result_factory=lambda c, k: MockResult([{"missing_count": 5}]))
        result = RequiredPropertyCheck().check(_simple_schema(), session=session)
        assert result.status == CheckStatus.FAILED
        assert "missing_entries" in result.details
        assert result.details["missing_entries"][0]["missing_count"] == 5

    def test_multiple_required_properties_aggregate(self) -> None:
        """Two labels each with one required property, both missing → 2 missing entries."""
        schema = SchemaDefinition(
            labels={
                "Vessel": LabelSchema(
                    properties={"mmsi": PropertySchema(expected_type="str")},
                    required_properties=frozenset({"mmsi"}),
                ),
                "Port": LabelSchema(
                    properties={"name": PropertySchema(expected_type="str")},
                    required_properties=frozenset({"name"}),
                ),
            }
        )
        session = MockSession(result_factory=lambda c, k: MockResult([{"missing_count": 1}]))
        result = RequiredPropertyCheck().check(schema, session=session)
        assert result.status == CheckStatus.FAILED
        assert len(result.details["missing_entries"]) == 2

    def test_exception_fails(self) -> None:
        """Neo4j error → FAILED."""
        session = _error_session(ConnectionError("neo4j down"))
        result = RequiredPropertyCheck().check(_simple_schema(), session=session)
        assert result.status == CheckStatus.FAILED
        assert "error" in result.details

    def test_no_required_properties_passes_with_zero_queries(self) -> None:
        """Schema label has no required_properties → PASSED, 0 queries."""
        schema = SchemaDefinition(
            labels={
                "Thing": LabelSchema(
                    properties={"name": PropertySchema(expected_type="str")},
                    required_properties=frozenset(),
                )
            }
        )
        session = MockSession()
        result = RequiredPropertyCheck().check(schema, session=session)
        assert result.status == CheckStatus.PASSED
        assert session.call_count == 0

    def test_passed_details_checked_pairs(self) -> None:
        """PASSED result has 'checked_pairs' detail."""
        session = MockSession(result_factory=lambda c, k: MockResult([{"missing_count": 0}]))
        result = RequiredPropertyCheck().check(_simple_schema(), session=session)
        assert "checked_pairs" in result.details
        assert result.details["checked_pairs"] == 1

    def test_total_missing_summed_in_message(self) -> None:
        """FAILED message includes total count of missing nodes."""
        schema = SchemaDefinition(
            labels={
                "Vessel": LabelSchema(
                    properties={"mmsi": PropertySchema(expected_type="str")},
                    required_properties=frozenset({"mmsi"}),
                ),
            }
        )
        session = MockSession(result_factory=lambda c, k: MockResult([{"missing_count": 7}]))
        result = RequiredPropertyCheck().check(schema, session=session)
        assert result.status == CheckStatus.FAILED
        assert "7" in result.message


# =============================================================================
# TC-CE03: EnumValueCheck
# =============================================================================


@pytest.mark.unit
class TestEnumValueCheckOnline:
    """EnumValueCheck with mocked session."""

    def test_session_none_skipped(self) -> None:
        """session=None → SKIPPED."""
        result = EnumValueCheck().check(_simple_schema(), session=None)
        assert result.status == CheckStatus.SKIPPED

    def test_valid_enum_values_passes(self) -> None:
        """bad_count=0 → PASSED."""

        def factory(cypher: str, kwargs: dict) -> MockResult:
            return MockResult([{"bad_count": 0, "sample_bad": []}])

        session = MockSession(result_factory=factory)
        result = EnumValueCheck().check(_simple_schema(), session=session)
        assert result.status == CheckStatus.PASSED
        # Only vesselType has enum_values; mmsi does not.
        assert session.call_count == 1

    def test_enum_violations_fails(self) -> None:
        """bad_count=3 with sample → FAILED with violation details."""

        def factory(cypher: str, kwargs: dict) -> MockResult:
            return MockResult([{"bad_count": 3, "sample_bad": ["SUBMARINE"]}])

        session = MockSession(result_factory=factory)
        result = EnumValueCheck().check(_simple_schema(), session=session)
        assert result.status == CheckStatus.FAILED
        assert "violations" in result.details
        v = result.details["violations"][0]
        assert v["bad_count"] == 3
        assert "SUBMARINE" in v["sample_bad_values"]

    def test_no_enum_properties_passes_with_zero_queries(self) -> None:
        """Schema without any enum_values → PASSED, 0 queries."""
        schema = SchemaDefinition(
            labels={
                "Thing": LabelSchema(
                    properties={"name": PropertySchema(expected_type="str")}
                )
            }
        )
        session = MockSession()
        result = EnumValueCheck().check(schema, session=session)
        assert result.status == CheckStatus.PASSED
        assert session.call_count == 0

    def test_exception_fails(self) -> None:
        """Exception → FAILED."""
        session = _error_session(RuntimeError("boom"))
        result = EnumValueCheck().check(_simple_schema(), session=session)
        assert result.status == CheckStatus.FAILED
        assert "error" in result.details

    def test_allowed_parameter_passed_to_session(self) -> None:
        """session.run is called with 'allowed' kwarg containing enum values."""
        captured: list[dict] = []

        def factory(cypher: str, kwargs: dict) -> MockResult:
            captured.append(kwargs)
            return MockResult([{"bad_count": 0, "sample_bad": []}])

        session = MockSession(result_factory=factory)
        EnumValueCheck().check(_simple_schema(), session=session)
        assert len(captured) == 1
        assert "allowed" in captured[0]
        assert set(captured[0]["allowed"]) == {"CARGO", "TANKER"}

    def test_passed_details_checked_pairs(self) -> None:
        """PASSED result has 'checked_pairs' = 1 for schema with one enum."""
        session = MockSession(
            result_factory=lambda c, k: MockResult([{"bad_count": 0, "sample_bad": []}])
        )
        result = EnumValueCheck().check(_simple_schema(), session=session)
        assert result.status == CheckStatus.PASSED
        assert result.details["checked_pairs"] == 1

    def test_multiple_enum_violations_summed(self) -> None:
        """Two enum properties both violating → total_bad reported."""
        schema = SchemaDefinition(
            labels={
                "Ship": LabelSchema(
                    properties={
                        "type": PropertySchema(
                            expected_type="str",
                            enum_values=frozenset({"A", "B"}),
                        ),
                        "flag": PropertySchema(
                            expected_type="str",
                            enum_values=frozenset({"RED", "BLUE"}),
                        ),
                    }
                )
            }
        )
        session = MockSession(
            result_factory=lambda c, k: MockResult([{"bad_count": 2, "sample_bad": ["X"]}])
        )
        result = EnumValueCheck().check(schema, session=session)
        assert result.status == CheckStatus.FAILED
        assert len(result.details["violations"]) == 2


# =============================================================================
# TC-CE04: CardinalityCheck
# =============================================================================


@pytest.mark.unit
class TestCardinalityCheckOnline:
    """CardinalityCheck with mocked session."""

    def _constrained_schema(self) -> SchemaDefinition:
        """Schema with min_cardinality=1 and max_cardinality=10."""
        return SchemaDefinition(
            labels={
                "Vessel": LabelSchema(
                    properties={
                        "mmsi": PropertySchema(
                            expected_type="str",
                            min_cardinality=1,
                            max_cardinality=10,
                        ),
                    }
                )
            }
        )

    def _min_only_schema(self) -> SchemaDefinition:
        """Schema with only min_cardinality=1."""
        return SchemaDefinition(
            labels={
                "Vessel": LabelSchema(
                    properties={
                        "mmsi": PropertySchema(
                            expected_type="str",
                            min_cardinality=1,
                        ),
                    }
                )
            }
        )

    def test_session_none_skipped(self) -> None:
        """session=None → SKIPPED."""
        result = CardinalityCheck().check(self._constrained_schema(), session=None)
        assert result.status == CheckStatus.SKIPPED

    def test_no_constraints_in_schema_skipped(self) -> None:
        """Schema with only default cardinality (min=0, max=None) → SKIPPED."""
        result = CardinalityCheck().check(_simple_schema(), session=MockSession())
        assert result.status == CheckStatus.SKIPPED
        assert result.details.get("reason") == "no_constraints"

    def test_clean_data_passes(self) -> None:
        """bad_count=0 for both min and max checks → PASSED."""
        session = MockSession(result_factory=lambda c, k: MockResult([{"bad_count": 0}]))
        result = CardinalityCheck().check(self._constrained_schema(), session=session)
        assert result.status == CheckStatus.PASSED
        # Two queries: one for min, one for max
        assert session.call_count == 2

    def test_min_violation_fails(self) -> None:
        """Nodes below minimum degree → FAILED."""
        call_index = [0]

        def factory(cypher: str, kwargs: dict) -> MockResult:
            # First call is for min_card check, return violations
            count = 4 if call_index[0] == 0 else 0
            call_index[0] += 1
            return MockResult([{"bad_count": count}])

        session = MockSession(result_factory=factory)
        result = CardinalityCheck().check(self._constrained_schema(), session=session)
        assert result.status == CheckStatus.FAILED
        assert "violations" in result.details

    def test_max_violation_fails(self) -> None:
        """Nodes above maximum degree → FAILED."""
        call_index = [0]

        def factory(cypher: str, kwargs: dict) -> MockResult:
            # First call (min) passes, second (max) fails
            count = 0 if call_index[0] == 0 else 2
            call_index[0] += 1
            return MockResult([{"bad_count": count}])

        session = MockSession(result_factory=factory)
        result = CardinalityCheck().check(self._constrained_schema(), session=session)
        assert result.status == CheckStatus.FAILED

    def test_min_only_runs_one_query(self) -> None:
        """Schema with only min_cardinality runs exactly one query."""
        session = MockSession(result_factory=lambda c, k: MockResult([{"bad_count": 0}]))
        result = CardinalityCheck().check(self._min_only_schema(), session=session)
        assert result.status == CheckStatus.PASSED
        assert session.call_count == 1

    def test_exception_fails(self) -> None:
        """Exception during query → FAILED."""
        session = _error_session(RuntimeError("query error"))
        result = CardinalityCheck().check(self._constrained_schema(), session=session)
        assert result.status == CheckStatus.FAILED
        assert "error" in result.details

    def test_passed_details_contain_constrained_labels(self) -> None:
        """PASSED result lists constrained labels in details."""
        session = MockSession(result_factory=lambda c, k: MockResult([{"bad_count": 0}]))
        result = CardinalityCheck().check(self._constrained_schema(), session=session)
        assert result.status == CheckStatus.PASSED
        assert "constrained_labels" in result.details
        assert "Vessel" in result.details["constrained_labels"]


# =============================================================================
# TC-CE05: OrphanNodeCheck
# =============================================================================


@pytest.mark.unit
class TestOrphanNodeCheckOnline:
    """OrphanNodeCheck with mocked session."""

    def test_session_none_skipped(self) -> None:
        """session=None → SKIPPED."""
        result = OrphanNodeCheck().check(_simple_schema(), session=None)
        assert result.status == CheckStatus.SKIPPED

    def test_no_orphans_passes(self) -> None:
        """orphan_count=0 for all labels → PASSED."""
        session = MockSession(result_factory=lambda c, k: MockResult([{"orphan_count": 0}]))
        result = OrphanNodeCheck().check(_simple_schema(), session=session)
        assert result.status == CheckStatus.PASSED
        assert result.details["total_orphans"] == 0

    def test_orphans_found_warning(self) -> None:
        """orphan_count=3 for Vessel label → WARNING."""
        session = MockSession(result_factory=lambda c, k: MockResult([{"orphan_count": 3}]))
        result = OrphanNodeCheck().check(_simple_schema(), session=session)
        assert result.status == CheckStatus.WARNING
        assert result.details["total_orphans"] == 3
        assert len(result.details["by_label"]) == 1

    def test_empty_schema_checks_all_labels(self) -> None:
        """Empty schema → uses fallback query that groups by labels(n)."""
        # Return two records for the "check all" query
        records = [
            {"node_labels": ["Orphan"], "orphan_count": 2},
            {"node_labels": ["Stray"], "orphan_count": 1},
        ]
        session = MockSession(result_factory=lambda c, k: MockResult(records))
        result = OrphanNodeCheck().check(_empty_schema(), session=session)
        assert result.status == CheckStatus.WARNING
        assert result.details["total_orphans"] == 3
        # One query issued (the catch-all)
        assert session.call_count == 1

    def test_empty_schema_no_orphans_passes(self) -> None:
        """Empty schema → no orphan records returned → PASSED."""
        session = MockSession(result_factory=lambda c, k: MockResult([]))
        result = OrphanNodeCheck().check(_empty_schema(), session=session)
        assert result.status == CheckStatus.PASSED
        assert result.details["total_orphans"] == 0

    def test_exception_fails(self) -> None:
        """Exception → FAILED (not SKIPPED)."""
        session = _error_session(IOError("db error"))
        result = OrphanNodeCheck().check(_simple_schema(), session=session)
        assert result.status == CheckStatus.FAILED
        assert "error" in result.details

    def test_multiple_labels_accumulates_totals(self) -> None:
        """Two labels, each with 2 orphans → total = 4."""
        schema = SchemaDefinition(
            labels={
                "Vessel": LabelSchema(),
                "Port": LabelSchema(),
            }
        )
        session = MockSession(result_factory=lambda c, k: MockResult([{"orphan_count": 2}]))
        result = OrphanNodeCheck().check(schema, session=session)
        assert result.status == CheckStatus.WARNING
        assert result.details["total_orphans"] == 4

    def test_check_name(self) -> None:
        assert OrphanNodeCheck().name == "orphan_node"

    def test_requires_connection(self) -> None:
        assert OrphanNodeCheck().requires_connection is True


# =============================================================================
# TC-CE06: DanglingRelationshipCheck
# =============================================================================


@pytest.mark.unit
class TestDanglingRelationshipCheckOnline:
    """DanglingRelationshipCheck with mocked session."""

    def test_session_none_skipped(self) -> None:
        """session=None → SKIPPED."""
        result = DanglingRelationshipCheck().check(_simple_schema(), session=None)
        assert result.status == CheckStatus.SKIPPED

    def test_empty_schema_no_labels_skipped(self) -> None:
        """Schema with no labels → SKIPPED (cannot check without known labels)."""
        result = DanglingRelationshipCheck().check(
            _empty_schema(), session=MockSession()
        )
        assert result.status == CheckStatus.SKIPPED
        assert result.details.get("reason") == "no_labels_in_schema"

    def test_all_known_labels_passes(self) -> None:
        """All rel endpoint labels are in the schema → PASSED."""
        records = [
            {
                "rel_type": "DOCKED_AT",
                "start_labels": ["Vessel"],
                "end_labels": ["Vessel"],  # both known
                "rel_count": 10,
            }
        ]
        session = MockSession(result_factory=lambda c, k: MockResult(records))
        result = DanglingRelationshipCheck().check(_simple_schema(), session=session)
        assert result.status == CheckStatus.PASSED

    def test_unknown_start_label_warning(self) -> None:
        """Relationship with unknown start label → WARNING."""
        records = [
            {
                "rel_type": "LINKED_TO",
                "start_labels": ["UnknownEntity"],
                "end_labels": ["Vessel"],
                "rel_count": 5,
            }
        ]
        session = MockSession(result_factory=lambda c, k: MockResult(records))
        result = DanglingRelationshipCheck().check(_simple_schema(), session=session)
        assert result.status == CheckStatus.WARNING
        assert result.details["total_relationships"] == 5
        d = result.details["dangling"][0]
        assert "UnknownEntity" in d["unknown_start_labels"]

    def test_unknown_end_label_warning(self) -> None:
        """Relationship with unknown end label → WARNING."""
        records = [
            {
                "rel_type": "DOCKED_AT",
                "start_labels": ["Vessel"],
                "end_labels": ["GhostPort"],
                "rel_count": 3,
            }
        ]
        session = MockSession(result_factory=lambda c, k: MockResult(records))
        result = DanglingRelationshipCheck().check(_simple_schema(), session=session)
        assert result.status == CheckStatus.WARNING
        d = result.details["dangling"][0]
        assert "GhostPort" in d["unknown_end_labels"]

    def test_no_relationships_returned_passes(self) -> None:
        """Query returns no records → PASSED."""
        session = MockSession(result_factory=lambda c, k: MockResult([]))
        result = DanglingRelationshipCheck().check(_simple_schema(), session=session)
        assert result.status == CheckStatus.PASSED

    def test_exception_fails(self) -> None:
        """Exception → FAILED."""
        session = _error_session(RuntimeError("query failed"))
        result = DanglingRelationshipCheck().check(_simple_schema(), session=session)
        assert result.status == CheckStatus.FAILED
        assert "error" in result.details

    def test_known_labels_included_in_passed_details(self) -> None:
        """PASSED result details include known_labels list."""
        session = MockSession(result_factory=lambda c, k: MockResult([]))
        result = DanglingRelationshipCheck().check(_simple_schema(), session=session)
        assert result.status == CheckStatus.PASSED
        assert "known_labels" in result.details
        assert "Vessel" in result.details["known_labels"]

    def test_multiple_dangling_relationships_aggregated(self) -> None:
        """Multiple dangling rels → all captured, total_relationships summed."""
        records = [
            {
                "rel_type": "A",
                "start_labels": ["Ghost1"],
                "end_labels": ["Vessel"],
                "rel_count": 4,
            },
            {
                "rel_type": "B",
                "start_labels": ["Vessel"],
                "end_labels": ["Ghost2"],
                "rel_count": 6,
            },
        ]
        session = MockSession(result_factory=lambda c, k: MockResult(records))
        result = DanglingRelationshipCheck().check(_simple_schema(), session=session)
        assert result.status == CheckStatus.WARNING
        assert result.details["total_relationships"] == 10
        assert result.details["dangling_count"] == 2

    def test_check_name(self) -> None:
        assert DanglingRelationshipCheck().name == "dangling_relationship"

    def test_requires_connection(self) -> None:
        assert DanglingRelationshipCheck().requires_connection is True

    def test_mixed_known_and_unknown_only_unknown_flagged(self) -> None:
        """If start_labels has both known and unknown, only unknown is reported."""
        records = [
            {
                "rel_type": "HAS",
                "start_labels": ["Vessel", "Ghost"],
                "end_labels": ["Vessel"],
                "rel_count": 1,
            }
        ]
        session = MockSession(result_factory=lambda c, k: MockResult(records))
        result = DanglingRelationshipCheck().check(_simple_schema(), session=session)
        assert result.status == CheckStatus.WARNING
        d = result.details["dangling"][0]
        assert "Ghost" in d["unknown_start_labels"]
        assert "Vessel" not in d["unknown_start_labels"]
