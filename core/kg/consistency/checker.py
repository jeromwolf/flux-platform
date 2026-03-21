"""KG Consistency Checker orchestrator.

Provides ``KGConsistencyChecker``, the main entry point for running
consistency checks against a schema definition.  Supports fluent check
registration, offline-only runs, full online runs, and selective runs by
check name.

Usage::

    from kg.consistency import KGConsistencyChecker
    from kg.consistency.checks import SchemaDefinition, LabelSchema, PropertySchema

    schema = SchemaDefinition(
        labels={
            "Vessel": LabelSchema(
                properties={"vesselType": PropertySchema(expected_type="str")},
                required_properties=frozenset({"vesselType"}),
            )
        },
        relationship_types=frozenset({"DOCKED_AT", "OPERATED_BY"}),
    )

    checker = KGConsistencyChecker(schema)

    # Offline only (no Neo4j needed)
    report = checker.run_offline()
    print(report.summary)

    # Full run with Neo4j session
    with driver.session() as session:
        report = checker.run_all(session)
        print(report.summary)
"""

from __future__ import annotations

import logging
from typing import Any

from kg.consistency.checks import (
    CardinalityCheck,
    ConsistencyCheck,
    DanglingRelationshipCheck,
    EnumValueCheck,
    OrphanNodeCheck,
    PropertyTypeCheck,
    RequiredPropertyCheck,
    SchemaAlignmentCheck,
    SchemaDefinition,
)
from kg.quality_gate import GateReport

logger = logging.getLogger(__name__)

# Default set of built-in checks, in logical execution order.
_DEFAULT_CHECKS: list[ConsistencyCheck] = [
    SchemaAlignmentCheck(),       # offline — validate schema structure first
    PropertyTypeCheck(),          # online  — type correctness
    RequiredPropertyCheck(),      # online  — mandatory fields present
    EnumValueCheck(),             # online  — enum constraints
    CardinalityCheck(),           # online  — relationship degree constraints
    OrphanNodeCheck(),            # online  — isolated nodes
    DanglingRelationshipCheck(),  # online  — unknown endpoint labels
]


class KGConsistencyChecker:
    """Orchestrates consistency checks for a KG schema.

    All built-in checks are registered by default.  Additional checks can be
    added via ``add_check()`` for a fluent configuration experience.

    Args:
        schema: The schema definition to validate against.
        checks: Optional explicit list of checks.  Defaults to all seven
            built-in checks when ``None``.

    Example::

        checker = KGConsistencyChecker(schema)
        checker.add_check(MyCustomCheck())
        report = checker.run_offline()
    """

    def __init__(
        self,
        schema: SchemaDefinition,
        checks: list[ConsistencyCheck] | None = None,
    ) -> None:
        self._schema = schema
        self._checks: list[ConsistencyCheck] = (
            list(_DEFAULT_CHECKS) if checks is None else list(checks)
        )

    # ------------------------------------------------------------------
    # Fluent API
    # ------------------------------------------------------------------

    def add_check(self, check: ConsistencyCheck) -> KGConsistencyChecker:
        """Register an additional consistency check.

        Args:
            check: A ``ConsistencyCheck`` instance to append to the registry.

        Returns:
            This checker instance (fluent API).
        """
        self._checks.append(check)
        return self

    # ------------------------------------------------------------------
    # Run modes
    # ------------------------------------------------------------------

    def run_offline(self) -> GateReport:
        """Run only the checks that do not require a Neo4j connection.

        Iterates over all registered checks and executes those where
        ``requires_connection`` is ``False``.  Online checks are silently
        skipped (not included in the report).

        Returns:
            A ``GateReport`` containing results from offline checks only.
        """
        report = GateReport()
        offline_checks = [c for c in self._checks if not c.requires_connection]

        logger.info("Running %d offline consistency check(s)", len(offline_checks))

        for check in offline_checks:
            result = check.check(self._schema, session=None)
            report.add(result)
            logger.debug(
                "Check '%s': %s — %s",
                result.name,
                result.status.value,
                result.message,
            )

        verdict = "PASSED" if report.passed else "FAILED"
        logger.info(
            "Offline consistency checks %s (%d check(s))",
            verdict,
            len(report.checks),
        )

        return report

    def run_all(self, session: Any) -> GateReport:
        """Run ALL registered checks (offline and online).

        Args:
            session: An open Neo4j session (``neo4j.Session``).  Passed to
                every check; online checks use it and offline checks ignore
                it.

        Returns:
            A ``GateReport`` containing results from all checks.
        """
        report = GateReport()

        logger.info("Running %d consistency check(s) (all)", len(self._checks))

        for check in self._checks:
            result = check.check(self._schema, session=session)
            report.add(result)
            logger.debug(
                "Check '%s': %s — %s",
                result.name,
                result.status.value,
                result.message,
            )

        verdict = "PASSED" if report.passed else "FAILED"
        logger.info(
            "Consistency checks %s (%d check(s))",
            verdict,
            len(report.checks),
        )

        return report

    def run_checks(
        self,
        names: list[str],
        session: Any | None = None,
    ) -> GateReport:
        """Run a specific subset of checks by name.

        Checks are matched by their ``name`` property.  Unrecognised names
        are logged as warnings but do not cause an error.

        Args:
            names: List of check names to execute.
            session: Optional Neo4j session.  Online checks return SKIPPED
                when ``session`` is ``None``.

        Returns:
            A ``GateReport`` containing results for the requested checks.
        """
        name_set = set(names)
        selected = [c for c in self._checks if c.name in name_set]

        not_found = name_set - {c.name for c in selected}
        for unknown in sorted(not_found):
            logger.warning(
                "Consistency check '%s' not found in registry — skipping",
                unknown,
            )

        report = GateReport()

        logger.info(
            "Running %d consistency check(s) by name: %s",
            len(selected),
            ", ".join(c.name for c in selected),
        )

        for check in selected:
            result = check.check(self._schema, session=session)
            report.add(result)
            logger.debug(
                "Check '%s': %s — %s",
                result.name,
                result.status.value,
                result.message,
            )

        verdict = "PASSED" if report.passed else "FAILED"
        logger.info(
            "Selected consistency checks %s (%d check(s))",
            verdict,
            len(report.checks),
        )

        return report

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def check_names(self) -> list[str]:
        """Names of all registered checks in order.

        Returns:
            List of check name strings.
        """
        return [c.name for c in self._checks]

    @property
    def schema(self) -> SchemaDefinition:
        """The schema definition this checker operates against.

        Returns:
            The ``SchemaDefinition`` instance.
        """
        return self._schema
