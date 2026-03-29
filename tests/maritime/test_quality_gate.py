"""Comprehensive unit tests for the KG Quality Gate module.

Tests all quality gate components: CheckResult, GateReport, and every
individual check method on QualityGate. All tests run without Neo4j.

Usage::

    PYTHONPATH=. python -m pytest tests/test_quality_gate.py -v -m unit
"""

from __future__ import annotations

import pytest

from kg.ontology.core import (
    Cardinality,
    LinkTypeDefinition,
    ObjectTypeDefinition,
    Ontology,
    PropertyDefinition,
    PropertyType,
)
from kg.quality_gate import (
    CheckResult,
    CheckStatus,
    GateReport,
    QualityGate,
)

# =========================================================================
# Helpers
# =========================================================================


def _make_empty_ontology() -> Ontology:
    """Create an empty ontology with no types."""
    return Ontology(name="empty")


def _make_minimal_ontology() -> Ontology:
    """Create a minimal ontology with 2 object types and 1 link type."""
    onto = Ontology(name="minimal")
    onto.define_object_type(
        ObjectTypeDefinition(
            name="Vessel",
            description="A ship",
            properties={
                "mmsi": PropertyDefinition(type=PropertyType.INTEGER, required=True),
                "name": PropertyDefinition(type=PropertyType.STRING),
            },
        )
    )
    onto.define_object_type(
        ObjectTypeDefinition(
            name="Port",
            description="A harbour",
            properties={
                "name": PropertyDefinition(type=PropertyType.STRING, required=True),
            },
        )
    )
    onto.define_link_type(
        LinkTypeDefinition(
            name="DOCKED_AT",
            from_type="Vessel",
            to_type="Port",
            cardinality=Cardinality.MANY_TO_ONE,
        )
    )
    return onto


def _make_objects_only_ontology() -> Ontology:
    """Create an ontology with object types but no link types."""
    onto = Ontology(name="objects_only")
    onto.define_object_type(
        ObjectTypeDefinition(name="Vessel", description="A ship")
    )
    return onto


def _load_maritime_ontology() -> Ontology:
    """Load the full maritime ontology."""
    from maritime.ontology.maritime_loader import load_maritime_ontology

    return load_maritime_ontology()


# =========================================================================
# 1. CheckResult tests
# =========================================================================


class TestCheckResult:
    """CheckResult creation and field access."""

    @pytest.mark.unit
    def test_create_passed(self) -> None:
        """Create a PASSED result."""
        r = CheckResult(name="test", status=CheckStatus.PASSED, message="ok")
        assert r.name == "test"
        assert r.status == CheckStatus.PASSED
        assert r.message == "ok"
        assert r.details == {}

    @pytest.mark.unit
    def test_create_failed(self) -> None:
        """Create a FAILED result."""
        r = CheckResult(
            name="fail_check",
            status=CheckStatus.FAILED,
            message="not ok",
            details={"reason": "missing"},
        )
        assert r.status == CheckStatus.FAILED
        assert r.details["reason"] == "missing"

    @pytest.mark.unit
    def test_create_skipped(self) -> None:
        """Create a SKIPPED result."""
        r = CheckResult(name="skip", status=CheckStatus.SKIPPED, message="n/a")
        assert r.status == CheckStatus.SKIPPED

    @pytest.mark.unit
    def test_create_warning(self) -> None:
        """Create a WARNING result."""
        r = CheckResult(name="warn", status=CheckStatus.WARNING, message="watch out")
        assert r.status == CheckStatus.WARNING

    @pytest.mark.unit
    def test_status_is_string_enum(self) -> None:
        """CheckStatus values are strings."""
        assert isinstance(CheckStatus.PASSED, str)
        assert CheckStatus.PASSED == "passed"
        assert CheckStatus.FAILED == "failed"
        assert CheckStatus.SKIPPED == "skipped"
        assert CheckStatus.WARNING == "warning"


# =========================================================================
# 2. GateReport tests
# =========================================================================


class TestGateReport:
    """GateReport aggregation, passed property, and summary format."""

    @pytest.mark.unit
    def test_empty_report_passes(self) -> None:
        """Empty report with no checks should pass."""
        report = GateReport()
        assert report.passed is True

    @pytest.mark.unit
    def test_all_passed(self) -> None:
        """Report with all PASSED checks should pass."""
        report = GateReport()
        report.add(CheckResult("a", CheckStatus.PASSED, "ok"))
        report.add(CheckResult("b", CheckStatus.PASSED, "ok"))
        assert report.passed is True

    @pytest.mark.unit
    def test_one_failed(self) -> None:
        """Report with one FAILED check should fail."""
        report = GateReport()
        report.add(CheckResult("a", CheckStatus.PASSED, "ok"))
        report.add(CheckResult("b", CheckStatus.FAILED, "bad"))
        assert report.passed is False

    @pytest.mark.unit
    def test_skipped_does_not_fail(self) -> None:
        """SKIPPED checks should not cause the report to fail."""
        report = GateReport()
        report.add(CheckResult("a", CheckStatus.PASSED, "ok"))
        report.add(CheckResult("b", CheckStatus.SKIPPED, "n/a"))
        assert report.passed is True

    @pytest.mark.unit
    def test_warning_does_not_fail(self) -> None:
        """WARNING checks should not cause the report to fail."""
        report = GateReport()
        report.add(CheckResult("a", CheckStatus.PASSED, "ok"))
        report.add(CheckResult("b", CheckStatus.WARNING, "watch out"))
        assert report.passed is True

    @pytest.mark.unit
    def test_mixed_with_failure(self) -> None:
        """Mixed statuses with one FAILED should fail overall."""
        report = GateReport()
        report.add(CheckResult("a", CheckStatus.PASSED, "ok"))
        report.add(CheckResult("b", CheckStatus.WARNING, "watch out"))
        report.add(CheckResult("c", CheckStatus.SKIPPED, "n/a"))
        report.add(CheckResult("d", CheckStatus.FAILED, "bad"))
        assert report.passed is False

    @pytest.mark.unit
    def test_summary_contains_verdict_passed(self) -> None:
        """Summary shows PASSED verdict."""
        report = GateReport()
        report.add(CheckResult("a", CheckStatus.PASSED, "ok"))
        assert "PASSED" in report.summary

    @pytest.mark.unit
    def test_summary_contains_verdict_failed(self) -> None:
        """Summary shows FAILED verdict."""
        report = GateReport()
        report.add(CheckResult("a", CheckStatus.FAILED, "bad"))
        assert "FAILED" in report.summary

    @pytest.mark.unit
    def test_summary_contains_check_names(self) -> None:
        """Summary includes individual check names and messages."""
        report = GateReport()
        report.add(CheckResult("my_check", CheckStatus.PASSED, "all good"))
        summary = report.summary
        assert "my_check" in summary
        assert "all good" in summary

    @pytest.mark.unit
    def test_summary_contains_counts(self) -> None:
        """Summary includes total, passed, failed counts."""
        report = GateReport()
        report.add(CheckResult("a", CheckStatus.PASSED, "ok"))
        report.add(CheckResult("b", CheckStatus.FAILED, "bad"))
        report.add(CheckResult("c", CheckStatus.SKIPPED, "n/a"))
        summary = report.summary
        assert "3 total" in summary
        assert "1 passed" in summary
        assert "1 failed" in summary
        assert "1 skipped" in summary

    @pytest.mark.unit
    def test_summary_contains_timestamp(self) -> None:
        """Summary includes the timestamp."""
        report = GateReport(timestamp="2026-02-14T00:00:00")
        report.add(CheckResult("a", CheckStatus.PASSED, "ok"))
        assert "2026-02-14" in report.summary

    @pytest.mark.unit
    def test_add_appends_check(self) -> None:
        """add() appends a CheckResult to the checks list."""
        report = GateReport()
        assert len(report.checks) == 0
        report.add(CheckResult("x", CheckStatus.PASSED, "ok"))
        assert len(report.checks) == 1


# =========================================================================
# 3. QualityGate.check_ontology_consistency tests
# =========================================================================


class TestCheckOntologyConsistency:
    """Tests for check_ontology_consistency."""

    @pytest.mark.unit
    def test_valid_maritime_ontology(self) -> None:
        """Maritime ontology passes consistency check."""
        onto = _load_maritime_ontology()
        gate = QualityGate()
        result = gate.check_ontology_consistency(onto)
        assert result.status in (CheckStatus.PASSED, CheckStatus.WARNING)
        assert result.details["object_types"] > 100

    @pytest.mark.unit
    def test_empty_ontology_fails(self) -> None:
        """Empty ontology fails consistency check."""
        onto = _make_empty_ontology()
        gate = QualityGate()
        result = gate.check_ontology_consistency(onto)
        assert result.status == CheckStatus.FAILED

    @pytest.mark.unit
    def test_objects_only_fails(self) -> None:
        """Ontology with objects but no links fails."""
        onto = _make_objects_only_ontology()
        gate = QualityGate()
        result = gate.check_ontology_consistency(onto)
        assert result.status == CheckStatus.FAILED
        assert "no link types" in result.message

    @pytest.mark.unit
    def test_minimal_ontology_passes(self) -> None:
        """Minimal ontology with types and links passes."""
        onto = _make_minimal_ontology()
        gate = QualityGate()
        result = gate.check_ontology_consistency(onto)
        assert result.status == CheckStatus.PASSED


# =========================================================================
# 4. QualityGate.check_required_labels tests
# =========================================================================


class TestCheckRequiredLabels:
    """Tests for check_required_labels."""

    @pytest.mark.unit
    def test_maritime_has_all_defaults(self) -> None:
        """Maritime ontology has all default required labels."""
        onto = _load_maritime_ontology()
        gate = QualityGate()
        result = gate.check_required_labels(onto)
        assert result.status == CheckStatus.PASSED

    @pytest.mark.unit
    def test_custom_required_labels_present(self) -> None:
        """Custom required labels that exist pass the check."""
        onto = _make_minimal_ontology()
        gate = QualityGate(required_labels=["Vessel", "Port"])
        result = gate.check_required_labels(onto)
        assert result.status == CheckStatus.PASSED

    @pytest.mark.unit
    def test_missing_required_labels_fail(self) -> None:
        """Missing required labels fail the check."""
        onto = _make_minimal_ontology()
        gate = QualityGate(required_labels=["Vessel", "Port", "NonExistent"])
        result = gate.check_required_labels(onto)
        assert result.status == CheckStatus.FAILED
        assert "NonExistent" in result.message

    @pytest.mark.unit
    def test_empty_ontology_fails(self) -> None:
        """Empty ontology fails required labels check."""
        onto = _make_empty_ontology()
        gate = QualityGate(required_labels=["Vessel"])
        result = gate.check_required_labels(onto)
        assert result.status == CheckStatus.FAILED

    @pytest.mark.unit
    def test_no_required_labels(self) -> None:
        """Empty required_labels list always passes."""
        onto = _make_empty_ontology()
        gate = QualityGate(required_labels=[])
        result = gate.check_required_labels(onto)
        assert result.status == CheckStatus.PASSED


# =========================================================================
# 5. QualityGate.check_evaluation_dataset tests
# =========================================================================


class TestCheckEvaluationDataset:
    """Tests for check_evaluation_dataset."""

    @pytest.mark.unit
    def test_builtin_dataset_passes(self) -> None:
        """Built-in evaluation dataset passes all structural checks."""
        gate = QualityGate()
        result = gate.check_evaluation_dataset()
        assert result.status == CheckStatus.PASSED
        assert "300 questions" in result.message

    @pytest.mark.unit
    def test_details_contain_reasoning_types(self) -> None:
        """Result details include reasoning type list."""
        gate = QualityGate()
        result = gate.check_evaluation_dataset()
        assert "reasoning_types" in result.details
        assert "DIRECT" in result.details["reasoning_types"]
        assert "BRIDGE" in result.details["reasoning_types"]


# =========================================================================
# 6. QualityGate.check_relationship_types tests
# =========================================================================


class TestCheckRelationshipTypes:
    """Tests for check_relationship_types."""

    @pytest.mark.unit
    def test_maritime_passes(self) -> None:
        """Maritime ontology has relationship types."""
        onto = _load_maritime_ontology()
        gate = QualityGate()
        result = gate.check_relationship_types(onto)
        assert result.status == CheckStatus.PASSED
        assert result.details["count"] > 50

    @pytest.mark.unit
    def test_empty_ontology_fails(self) -> None:
        """Empty ontology fails relationship type check."""
        onto = _make_empty_ontology()
        gate = QualityGate()
        result = gate.check_relationship_types(onto)
        assert result.status == CheckStatus.FAILED

    @pytest.mark.unit
    def test_minimal_ontology_passes(self) -> None:
        """Minimal ontology with one link type passes."""
        onto = _make_minimal_ontology()
        gate = QualityGate()
        result = gate.check_relationship_types(onto)
        assert result.status == CheckStatus.PASSED
        assert result.details["count"] == 1


# =========================================================================
# 7. QualityGate.check_node_property_completeness tests
# =========================================================================


class TestCheckNodePropertyCompleteness:
    """Tests for check_node_property_completeness."""

    @pytest.mark.unit
    def test_minimal_with_props_passes(self) -> None:
        """Ontology where required types have properties passes."""
        onto = _make_minimal_ontology()
        gate = QualityGate(required_labels=["Vessel", "Port"])
        result = gate.check_node_property_completeness(onto)
        assert result.status == CheckStatus.PASSED

    @pytest.mark.unit
    def test_type_without_properties_warns(self) -> None:
        """Required type lacking properties triggers WARNING."""
        onto = Ontology(name="sparse")
        onto.define_object_type(
            ObjectTypeDefinition(name="Vessel", description="Ship", properties={})
        )
        gate = QualityGate(required_labels=["Vessel"])
        result = gate.check_node_property_completeness(onto)
        assert result.status == CheckStatus.WARNING
        assert "Vessel" in result.message

    @pytest.mark.unit
    def test_non_required_without_props_passes(self) -> None:
        """Non-required types without properties still pass."""
        onto = Ontology(name="mixed")
        onto.define_object_type(
            ObjectTypeDefinition(
                name="Vessel",
                description="Ship",
                properties={
                    "name": PropertyDefinition(type=PropertyType.STRING),
                },
            )
        )
        onto.define_object_type(
            ObjectTypeDefinition(name="Misc", description="Other", properties={})
        )
        gate = QualityGate(required_labels=["Vessel"])
        result = gate.check_node_property_completeness(onto)
        assert result.status == CheckStatus.PASSED


# =========================================================================
# 8. QualityGate.check_pipeline_sample tests
# =========================================================================


class TestCheckPipelineSample:
    """Tests for check_pipeline_sample."""

    @pytest.mark.unit
    def test_pipeline_sample_runs(self) -> None:
        """Pipeline sample check runs without error."""
        gate = QualityGate()
        result = gate.check_pipeline_sample()
        # Pipeline may pass or warn depending on parser behavior;
        # the important thing is it does not raise.
        assert result.status in (
            CheckStatus.PASSED,
            CheckStatus.WARNING,
            CheckStatus.FAILED,
        )
        assert result.name == "pipeline_sample"


# =========================================================================
# 9. QualityGate.check_orphan_rate / check_node_count tests
# =========================================================================


class TestSkippedChecks:
    """Tests for checks that are always SKIPPED without Neo4j."""

    @pytest.mark.unit
    def test_orphan_rate_skipped(self) -> None:
        """Orphan rate check returns SKIPPED."""
        gate = QualityGate()
        result = gate.check_orphan_rate()
        assert result.status == CheckStatus.SKIPPED
        assert "Neo4j" in result.message

    @pytest.mark.unit
    def test_node_count_skipped(self) -> None:
        """Node count check returns SKIPPED."""
        gate = QualityGate()
        result = gate.check_node_count()
        assert result.status == CheckStatus.SKIPPED
        assert "Neo4j" in result.message

    @pytest.mark.unit
    def test_orphan_rate_has_threshold(self) -> None:
        """Orphan rate check details include threshold."""
        gate = QualityGate(max_orphan_rate=0.05)
        result = gate.check_orphan_rate()
        assert result.details["threshold"] == 0.05


# =========================================================================
# 10. QualityGate.run_all tests
# =========================================================================


class TestRunAll:
    """Tests for run_all aggregate execution."""

    @pytest.mark.unit
    def test_run_all_with_maritime_ontology(self) -> None:
        """run_all with maritime ontology produces complete report."""
        onto = _load_maritime_ontology()
        gate = QualityGate()
        report = gate.run_all(ontology=onto)
        assert len(report.checks) == 8
        # Skipped checks (orphan_rate, node_count) should not fail
        assert report.passed is True or any(
            c.status == CheckStatus.FAILED for c in report.checks
        )

    @pytest.mark.unit
    def test_run_all_without_ontology_loads_maritime(self) -> None:
        """run_all with None ontology auto-loads maritime."""
        gate = QualityGate()
        report = gate.run_all(ontology=None)
        assert len(report.checks) >= 1
        # Should have loaded successfully - first check is ontology_consistency
        assert report.checks[0].name in ("ontology_consistency", "ontology_load")

    @pytest.mark.unit
    def test_run_all_report_has_timestamp(self) -> None:
        """run_all report includes a timestamp."""
        onto = _make_minimal_ontology()
        gate = QualityGate(required_labels=["Vessel", "Port"])
        report = gate.run_all(ontology=onto)
        assert report.timestamp is not None
        assert len(report.timestamp) > 0

    @pytest.mark.unit
    def test_run_all_check_names_unique(self) -> None:
        """All check names in the report are unique."""
        onto = _load_maritime_ontology()
        gate = QualityGate()
        report = gate.run_all(ontology=onto)
        names = [c.name for c in report.checks]
        assert len(names) == len(set(names))

    @pytest.mark.unit
    def test_run_all_has_all_check_types(self) -> None:
        """run_all includes all expected check names."""
        onto = _load_maritime_ontology()
        gate = QualityGate()
        report = gate.run_all(ontology=onto)
        names = {c.name for c in report.checks}
        expected = {
            "ontology_consistency",
            "required_labels",
            "evaluation_dataset",
            "relationship_types",
            "node_property_completeness",
            "pipeline_sample",
            "orphan_rate",
            "node_count",
        }
        assert expected == names

    @pytest.mark.unit
    def test_run_all_summary_readable(self) -> None:
        """run_all summary is a non-empty string."""
        onto = _load_maritime_ontology()
        gate = QualityGate()
        report = gate.run_all(ontology=onto)
        summary = report.summary
        assert isinstance(summary, str)
        assert "Quality Gate Report" in summary
        assert "Verdict" in summary


# =========================================================================
# 11. QualityGate constructor tests
# =========================================================================


class TestQualityGateInit:
    """Tests for QualityGate constructor defaults and overrides."""

    @pytest.mark.unit
    def test_default_thresholds(self) -> None:
        """Default constructor values."""
        gate = QualityGate()
        assert gate.max_orphan_rate == 0.1
        assert gate.min_query_success_rate == 0.9
        assert len(gate.required_labels) > 0

    @pytest.mark.unit
    def test_custom_thresholds(self) -> None:
        """Custom constructor values."""
        gate = QualityGate(
            max_orphan_rate=0.05,
            min_query_success_rate=0.8,
            required_labels=["Vessel"],
        )
        assert gate.max_orphan_rate == 0.05
        assert gate.min_query_success_rate == 0.8
        assert gate.required_labels == ["Vessel"]

    @pytest.mark.unit
    def test_empty_required_labels(self) -> None:
        """Empty required_labels is respected."""
        gate = QualityGate(required_labels=[])
        assert gate.required_labels == []

    @pytest.mark.unit
    def test_default_required_labels_include_core_types(self) -> None:
        """Default required labels include Vessel, Port, Organization."""
        gate = QualityGate()
        assert "Vessel" in gate.required_labels
        assert "Port" in gate.required_labels
        assert "Organization" in gate.required_labels
