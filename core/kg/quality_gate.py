"""KG Quality Gate for CI/CD pipeline.

Automated quality checks to prevent deployment when KG quality
falls below configurable thresholds. Per GraphRAG Part 12 enterprise patterns.

Checks run WITHOUT a Neo4j connection (unit-test friendly). They validate:
- Ontology structure (object types exist, link types exist)
- Evaluation dataset completeness (300 questions, balanced distribution)
- Pipeline functionality (can generate Cypher from sample questions)
- Relationship type coverage
- Node property completeness

For checks that WOULD need Neo4j (orphan rate, live node count), the gate
returns SKIPPED status with an explanatory message.

Usage::

    gate = QualityGate()
    report = gate.run_all()
    if not report.passed:
        sys.exit(1)

CLI::

    python -m kg.quality_gate
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CheckStatus(str, Enum):
    """Status of an individual quality gate check."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    WARNING = "warning"


@dataclass
class CheckResult:
    """Result of a single quality gate check.

    Attributes:
        name: Human-readable check name.
        status: Pass/fail/skip/warning status.
        message: One-line summary of the result.
        details: Arbitrary key-value details for diagnostics.
    """

    name: str
    status: CheckStatus
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class GateReport:
    """Aggregated quality gate report.

    Attributes:
        checks: Ordered list of individual check results.
        timestamp: ISO 8601 timestamp of the gate run.
    """

    checks: list[CheckResult] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def passed(self) -> bool:
        """True if no checks have FAILED status."""
        return all(c.status != CheckStatus.FAILED for c in self.checks)

    @property
    def summary(self) -> str:
        """Human-readable summary of the gate report."""
        total = len(self.checks)
        passed = sum(1 for c in self.checks if c.status == CheckStatus.PASSED)
        failed = sum(1 for c in self.checks if c.status == CheckStatus.FAILED)
        skipped = sum(1 for c in self.checks if c.status == CheckStatus.SKIPPED)
        warnings = sum(1 for c in self.checks if c.status == CheckStatus.WARNING)

        verdict = "PASSED" if self.passed else "FAILED"

        lines = [
            "=" * 60,
            "  KG Quality Gate Report",
            f"  Timestamp: {self.timestamp}",
            f"  Verdict:   {verdict}",
            f"  Checks:    {total} total, {passed} passed, {failed} failed, "
            f"{skipped} skipped, {warnings} warnings",
            "=" * 60,
        ]

        for c in self.checks:
            icon = {
                CheckStatus.PASSED: "[PASS]",
                CheckStatus.FAILED: "[FAIL]",
                CheckStatus.SKIPPED: "[SKIP]",
                CheckStatus.WARNING: "[WARN]",
            }.get(c.status, "[????]")
            lines.append(f"  {icon} {c.name}: {c.message}")

        lines.append("=" * 60)
        return "\n".join(lines)

    def add(self, result: CheckResult) -> None:
        """Append a check result to the report.

        Args:
            result: CheckResult to add.
        """
        self.checks.append(result)


# ---------------------------------------------------------------------------
# Default required labels (core maritime entities expected in any deployment)
# ---------------------------------------------------------------------------

_DEFAULT_REQUIRED_LABELS: list[str] = [
    "Vessel",
    "Port",
    "Voyage",
    "Organization",
    "Incident",
    "TestFacility",
    "Experiment",
    "Sensor",
    "Observation",
    "Role",
]


class QualityGate:
    """KG quality gate with configurable checks.

    All checks operate on ontology metadata and the evaluation dataset
    so they can run without a live Neo4j connection.

    Checks:
        1. Ontology consistency -- object types and link types are non-empty
        2. Required labels -- core maritime labels exist in the ontology
        3. Evaluation dataset -- builtin dataset has expected size and balance
        4. Relationship types -- ontology defines relationship types
        5. Node property completeness -- required properties defined
        6. Pipeline sample -- sample NL questions produce Cypher output
        7. Orphan rate (SKIPPED) -- would need Neo4j
        8. Node count (SKIPPED) -- would need Neo4j

    Args:
        max_orphan_rate: Maximum allowed orphan node ratio (for live checks).
        min_query_success_rate: Minimum required evaluation success rate.
        required_labels: Node labels that must exist. Defaults to core
            maritime labels.
    """

    def __init__(
        self,
        max_orphan_rate: float = 0.1,
        min_query_success_rate: float = 0.9,
        required_labels: list[str] | None = None,
    ) -> None:
        self.max_orphan_rate = max_orphan_rate
        self.min_query_success_rate = min_query_success_rate
        self.required_labels = (
            list(_DEFAULT_REQUIRED_LABELS) if required_labels is None
            else required_labels
        )

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def check_ontology_consistency(self, ontology: Any) -> CheckResult:
        """Verify ontology has non-empty object types and link types.

        Args:
            ontology: An Ontology instance from ``kg.ontology.core``.

        Returns:
            CheckResult with PASSED if both collections are non-empty,
            FAILED otherwise.
        """
        try:
            object_types = ontology.get_all_object_types()
            link_types = ontology.get_all_link_types()

            obj_count = len(object_types)
            link_count = len(link_types)

            if obj_count == 0 and link_count == 0:
                return CheckResult(
                    name="ontology_consistency",
                    status=CheckStatus.FAILED,
                    message="Ontology has no object types and no link types",
                    details={"object_types": obj_count, "link_types": link_count},
                )
            if obj_count == 0:
                return CheckResult(
                    name="ontology_consistency",
                    status=CheckStatus.FAILED,
                    message="Ontology has no object types defined",
                    details={"object_types": obj_count, "link_types": link_count},
                )
            if link_count == 0:
                return CheckResult(
                    name="ontology_consistency",
                    status=CheckStatus.FAILED,
                    message="Ontology has no link types defined",
                    details={"object_types": obj_count, "link_types": link_count},
                )

            # Run ontology's own validation
            is_valid, errors = ontology.validate()
            if not is_valid:
                return CheckResult(
                    name="ontology_consistency",
                    status=CheckStatus.WARNING,
                    message=(
                        f"Ontology has {obj_count} object types and "
                        f"{link_count} link types but {len(errors)} validation error(s)"
                    ),
                    details={
                        "object_types": obj_count,
                        "link_types": link_count,
                        "validation_errors": errors[:10],
                    },
                )

            return CheckResult(
                name="ontology_consistency",
                status=CheckStatus.PASSED,
                message=(
                    f"Ontology has {obj_count} object types and "
                    f"{link_count} link types, all valid"
                ),
                details={"object_types": obj_count, "link_types": link_count},
            )
        except Exception as exc:
            return CheckResult(
                name="ontology_consistency",
                status=CheckStatus.FAILED,
                message=f"Ontology consistency check error: {exc}",
                details={"error": str(exc)},
            )

    def check_required_labels(self, ontology: Any) -> CheckResult:
        """Verify required node labels exist in the ontology.

        Args:
            ontology: An Ontology instance from ``kg.ontology.core``.

        Returns:
            CheckResult with PASSED if all required labels are present,
            FAILED if any are missing.
        """
        try:
            existing_names = {ot.name for ot in ontology.get_all_object_types()}
            missing = [label for label in self.required_labels if label not in existing_names]

            if missing:
                return CheckResult(
                    name="required_labels",
                    status=CheckStatus.FAILED,
                    message=f"Missing {len(missing)} required label(s): {', '.join(missing)}",
                    details={
                        "missing": missing,
                        "required": self.required_labels,
                        "existing_count": len(existing_names),
                    },
                )

            return CheckResult(
                name="required_labels",
                status=CheckStatus.PASSED,
                message=(
                    f"All {len(self.required_labels)} required labels present "
                    f"(out of {len(existing_names)} total)"
                ),
                details={
                    "required": self.required_labels,
                    "existing_count": len(existing_names),
                },
            )
        except Exception as exc:
            return CheckResult(
                name="required_labels",
                status=CheckStatus.FAILED,
                message=f"Required labels check error: {exc}",
                details={"error": str(exc)},
            )

    def check_evaluation_dataset(self) -> CheckResult:
        """Validate the built-in evaluation dataset structure and balance.

        Checks:
        - Dataset has exactly 300 questions
        - 60 EASY, 100 MEDIUM, 140 HARD questions
        - All 5 reasoning types are represented
        - Every question has ground truth Cypher and expected labels

        Returns:
            CheckResult with PASSED if all structural requirements are met.
        """
        try:
            from maritime.evaluation.dataset import EvalDataset, Difficulty, ReasoningType

            dataset = EvalDataset.builtin()
            issues: list[str] = []

            # Total count
            total = len(dataset.questions)
            if total != 300:
                issues.append(f"Expected 300 questions, got {total}")

            # Difficulty distribution (60 EASY, 100 MEDIUM, 140 HARD)
            expected_counts = {
                Difficulty.EASY: 60,
                Difficulty.MEDIUM: 100,
                Difficulty.HARD: 140,
            }
            for diff in Difficulty:
                count = len(dataset.get_by_difficulty(diff))
                expected = expected_counts[diff]
                if count != expected:
                    issues.append(f"Expected {expected} {diff.value} questions, got {count}")

            # Reasoning type coverage
            present_types = {q.reasoning_type for q in dataset.questions}
            for rt in ReasoningType:
                if rt not in present_types:
                    issues.append(f"Missing reasoning type: {rt.value}")

            # Ground truth completeness
            missing_cypher = sum(
                1 for q in dataset.questions if not q.ground_truth_cypher
            )
            if missing_cypher > 0:
                issues.append(f"{missing_cypher} question(s) missing ground truth Cypher")

            missing_labels = sum(
                1 for q in dataset.questions if not q.expected_labels
            )
            if missing_labels > 0:
                issues.append(f"{missing_labels} question(s) missing expected labels")

            if issues:
                return CheckResult(
                    name="evaluation_dataset",
                    status=CheckStatus.FAILED,
                    message=f"Evaluation dataset has {len(issues)} issue(s)",
                    details={"issues": issues, "total_questions": total},
                )

            return CheckResult(
                name="evaluation_dataset",
                status=CheckStatus.PASSED,
                message=(
                    f"Evaluation dataset: {total} questions, "
                    f"balanced distribution, all ground truths present"
                ),
                details={
                    "total_questions": total,
                    "reasoning_types": sorted(rt.value for rt in present_types),
                },
            )
        except Exception as exc:
            return CheckResult(
                name="evaluation_dataset",
                status=CheckStatus.FAILED,
                message=f"Evaluation dataset check error: {exc}",
                details={"error": str(exc)},
            )

    def check_relationship_types(self, ontology: Any) -> CheckResult:
        """Verify relationship types are defined and reference valid endpoints.

        Args:
            ontology: An Ontology instance from ``kg.ontology.core``.

        Returns:
            CheckResult with PASSED if relationship types exist and are valid.
        """
        try:
            link_types = ontology.get_all_link_types()
            count = len(link_types)

            if count == 0:
                return CheckResult(
                    name="relationship_types",
                    status=CheckStatus.FAILED,
                    message="No relationship types defined in ontology",
                    details={"count": 0},
                )

            # Check all endpoints reference existing object types
            existing_names = {ot.name for ot in ontology.get_all_object_types()}
            broken: list[str] = []
            for lt in link_types:
                if lt.from_type not in existing_names:
                    broken.append(f"{lt.name}: unknown from_type '{lt.from_type}'")
                if lt.to_type not in existing_names:
                    broken.append(f"{lt.name}: unknown to_type '{lt.to_type}'")

            if broken:
                return CheckResult(
                    name="relationship_types",
                    status=CheckStatus.WARNING,
                    message=(
                        f"{count} relationship types defined, "
                        f"{len(broken)} have broken endpoint(s)"
                    ),
                    details={"count": count, "broken": broken[:10]},
                )

            return CheckResult(
                name="relationship_types",
                status=CheckStatus.PASSED,
                message=f"{count} relationship types defined, all endpoints valid",
                details={"count": count},
            )
        except Exception as exc:
            return CheckResult(
                name="relationship_types",
                status=CheckStatus.FAILED,
                message=f"Relationship types check error: {exc}",
                details={"error": str(exc)},
            )

    def check_node_property_completeness(self, ontology: Any) -> CheckResult:
        """Check that core entity types have property definitions.

        Verifies that at least the required label types have at least one
        property defined. Entity types with zero properties are flagged.

        Args:
            ontology: An Ontology instance from ``kg.ontology.core``.

        Returns:
            CheckResult with PASSED if core types have properties,
            WARNING if some types lack properties.
        """
        try:
            all_types = ontology.get_all_object_types()
            types_without_props: list[str] = []
            types_with_props: list[str] = []

            for ot in all_types:
                if len(ot.properties) == 0:
                    types_without_props.append(ot.name)
                else:
                    types_with_props.append(ot.name)

            total = len(all_types)
            with_props = len(types_with_props)
            without_props = len(types_without_props)

            # Check specifically required labels
            required_without = [
                label for label in self.required_labels
                if label in types_without_props
            ]

            if required_without:
                return CheckResult(
                    name="node_property_completeness",
                    status=CheckStatus.WARNING,
                    message=(
                        f"{without_props}/{total} types lack properties; "
                        f"required types missing properties: {', '.join(required_without)}"
                    ),
                    details={
                        "total_types": total,
                        "with_properties": with_props,
                        "without_properties": without_props,
                        "required_without_props": required_without,
                    },
                )

            if without_props > 0:
                return CheckResult(
                    name="node_property_completeness",
                    status=CheckStatus.PASSED,
                    message=(
                        f"{with_props}/{total} types have properties "
                        f"(all required labels covered)"
                    ),
                    details={
                        "total_types": total,
                        "with_properties": with_props,
                        "without_properties": without_props,
                    },
                )

            return CheckResult(
                name="node_property_completeness",
                status=CheckStatus.PASSED,
                message=f"All {total} types have property definitions",
                details={
                    "total_types": total,
                    "with_properties": with_props,
                    "without_properties": without_props,
                },
            )
        except Exception as exc:
            return CheckResult(
                name="node_property_completeness",
                status=CheckStatus.FAILED,
                message=f"Node property completeness check error: {exc}",
                details={"error": str(exc)},
            )

    def check_pipeline_sample(self) -> CheckResult:
        """Run a sample NL question through the Text-to-Cypher pipeline.

        Validates that the pipeline can parse Korean text and generate
        Cypher without errors. Does NOT require Neo4j.

        Returns:
            CheckResult with PASSED if sample queries produce Cypher.
        """
        try:
            from kg.pipeline import TextToCypherPipeline

            pipeline = TextToCypherPipeline()
            sample_questions = [
                "부산항 정보 알려줘",
                "컨테이너선 조회",
                "KRISO 시설 목록",
            ]

            successes = 0
            failures: list[str] = []
            for q in sample_questions:
                try:
                    output = pipeline.process(q)
                    if output.success and output.generated_query:
                        successes += 1
                    else:
                        failures.append(
                            f"'{q}': {output.error or 'no output'}"
                        )
                except Exception as exc:
                    failures.append(f"'{q}': {exc}")

            total = len(sample_questions)
            rate = successes / total if total > 0 else 0.0

            if rate >= self.min_query_success_rate:
                return CheckResult(
                    name="pipeline_sample",
                    status=CheckStatus.PASSED,
                    message=f"Pipeline succeeded on {successes}/{total} sample queries",
                    details={"successes": successes, "total": total, "rate": rate},
                )
            elif rate > 0:
                return CheckResult(
                    name="pipeline_sample",
                    status=CheckStatus.WARNING,
                    message=(
                        f"Pipeline succeeded on {successes}/{total} sample queries "
                        f"(below {self.min_query_success_rate:.0%} threshold)"
                    ),
                    details={
                        "successes": successes,
                        "total": total,
                        "rate": rate,
                        "failures": failures,
                    },
                )
            else:
                return CheckResult(
                    name="pipeline_sample",
                    status=CheckStatus.FAILED,
                    message=f"Pipeline failed on all {total} sample queries",
                    details={
                        "successes": 0,
                        "total": total,
                        "rate": 0.0,
                        "failures": failures,
                    },
                )
        except Exception as exc:
            return CheckResult(
                name="pipeline_sample",
                status=CheckStatus.FAILED,
                message=f"Pipeline sample check error: {exc}",
                details={"error": str(exc)},
            )

    def check_orphan_rate(self) -> CheckResult:
        """Check orphan node rate (requires Neo4j connection).

        This check is always SKIPPED in offline mode because it requires
        querying the live graph to count disconnected nodes.

        Returns:
            CheckResult with SKIPPED status.
        """
        return CheckResult(
            name="orphan_rate",
            status=CheckStatus.SKIPPED,
            message=(
                "Orphan rate check requires a live Neo4j connection "
                f"(threshold: {self.max_orphan_rate:.0%})"
            ),
            details={"threshold": self.max_orphan_rate, "reason": "no_neo4j"},
        )

    def check_node_count(self) -> CheckResult:
        """Check total node count (requires Neo4j connection).

        This check is always SKIPPED in offline mode because it requires
        querying the live graph database.

        Returns:
            CheckResult with SKIPPED status.
        """
        return CheckResult(
            name="node_count",
            status=CheckStatus.SKIPPED,
            message="Node count check requires a live Neo4j connection",
            details={"reason": "no_neo4j"},
        )

    # ------------------------------------------------------------------
    # Aggregate runner
    # ------------------------------------------------------------------

    def run_all(self, ontology: Any | None = None) -> GateReport:
        """Run all quality gate checks and return an aggregated report.

        If *ontology* is None, attempts to load the maritime ontology
        from ``kg.ontology.maritime_loader``.

        Args:
            ontology: Optional Ontology instance. Loaded automatically
                if not provided.

        Returns:
            GateReport with results from all checks.
        """
        if ontology is None:
            try:
                from maritime.ontology.maritime_loader import load_maritime_ontology

                ontology = load_maritime_ontology()
                logger.info("Loaded maritime ontology for quality gate")
            except Exception as exc:
                report = GateReport()
                report.add(
                    CheckResult(
                        name="ontology_load",
                        status=CheckStatus.FAILED,
                        message=f"Failed to load maritime ontology: {exc}",
                        details={"error": str(exc)},
                    )
                )
                return report

        report = GateReport()

        # 1. Ontology consistency
        report.add(self.check_ontology_consistency(ontology))

        # 2. Required labels
        report.add(self.check_required_labels(ontology))

        # 3. Evaluation dataset
        report.add(self.check_evaluation_dataset())

        # 4. Relationship types
        report.add(self.check_relationship_types(ontology))

        # 5. Node property completeness
        report.add(self.check_node_property_completeness(ontology))

        # 6. Pipeline sample
        report.add(self.check_pipeline_sample())

        # 7. Orphan rate (SKIPPED - needs Neo4j)
        report.add(self.check_orphan_rate())

        # 8. Node count (SKIPPED - needs Neo4j)
        report.add(self.check_node_count())

        verdict = "PASSED" if report.passed else "FAILED"
        logger.info("Quality gate %s (%d checks)", verdict, len(report.checks))

        return report


if __name__ == "__main__":
    import sys

    from maritime.ontology.maritime_loader import load_maritime_ontology

    logging.basicConfig(level=logging.INFO)
    ontology = load_maritime_ontology()
    gate = QualityGate()
    report = gate.run_all(ontology=ontology)
    print(report.summary)
    sys.exit(0 if report.passed else 1)
