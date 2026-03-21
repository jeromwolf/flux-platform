"""Consistency check primitives and built-in check implementations.

Provides the abstract base class ``ConsistencyCheck``, the frozen dataclass
hierarchy that describes a schema (``SchemaDefinition``, ``LabelSchema``,
``PropertySchema``), and seven built-in concrete checks.

Built-in checks:
    - SchemaAlignmentCheck  -- offline, validates schema definition itself
    - PropertyTypeCheck     -- online, validates node property types
    - RequiredPropertyCheck -- online, validates required properties present
    - EnumValueCheck        -- online, validates enum-constrained property values
    - CardinalityCheck      -- online, validates relationship cardinality
    - OrphanNodeCheck       -- online, finds nodes with no relationships
    - DanglingRelationshipCheck -- online, finds rels to unexpected labels
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from kg.quality_gate import CheckResult, CheckStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema definition dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PropertySchema:
    """Schema metadata for a single node property.

    Attributes:
        expected_type: One of "str", "int", "float", "bool", "datetime",
            "list", "point".
        enum_values: Allowed values when the property is an enumeration.
            ``None`` means unconstrained.
        min_cardinality: Minimum number of occurrences (default 0).
        max_cardinality: Maximum number of occurrences; ``None`` = unlimited.
    """

    expected_type: str
    enum_values: frozenset[str] | None = None
    min_cardinality: int = 0
    max_cardinality: int | None = None


@dataclass(frozen=True)
class LabelSchema:
    """Schema for all nodes sharing a given Neo4j label.

    Attributes:
        properties: Mapping of property name to its ``PropertySchema``.
        required_properties: Set of property names that must be present on
            every node with this label.
    """

    properties: dict[str, PropertySchema] = field(default_factory=dict)
    required_properties: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class SchemaDefinition:
    """Complete schema definition for a KG deployment.

    Attributes:
        labels: Mapping of Neo4j node label to its ``LabelSchema``.
        relationship_types: Set of all known relationship type names.
    """

    labels: dict[str, LabelSchema] = field(default_factory=dict)
    relationship_types: frozenset[str] = field(default_factory=frozenset)


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------


class ConsistencyCheck(ABC):
    """Abstract base for all KG consistency checks.

    Subclasses implement ``check()`` and declare whether they need a live
    Neo4j session via ``requires_connection``.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique machine-readable name for this check."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this check validates."""

    @property
    @abstractmethod
    def requires_connection(self) -> bool:
        """Whether this check requires a live Neo4j session."""

    @abstractmethod
    def check(
        self,
        schema: SchemaDefinition,
        session: Any | None = None,
    ) -> CheckResult:
        """Execute the consistency check.

        Args:
            schema: The schema definition to validate against.
            session: An open Neo4j session (``neo4j.Session``).  Must be
                provided when ``requires_connection`` is ``True``; if absent
                the check should return ``SKIPPED``.

        Returns:
            A ``CheckResult`` describing the outcome.
        """


# ---------------------------------------------------------------------------
# 1. SchemaAlignmentCheck (offline)
# ---------------------------------------------------------------------------


class SchemaAlignmentCheck(ConsistencyCheck):
    """Validates the schema definition itself without touching Neo4j.

    Checks performed:
    - No empty label names (empty string keys).
    - Required properties are a subset of defined properties for each label.
    - Enum values are non-empty when specified.
    - ``min_cardinality`` is non-negative and ``max_cardinality >= min`` when
      both are set.
    """

    @property
    def name(self) -> str:  # noqa: D102
        return "schema_alignment"

    @property
    def description(self) -> str:  # noqa: D102
        return (
            "Validates schema definition structure offline: no empty labels, "
            "required properties are defined, enum values non-empty."
        )

    @property
    def requires_connection(self) -> bool:  # noqa: D102
        return False

    def check(
        self,
        schema: SchemaDefinition,
        session: Any | None = None,
    ) -> CheckResult:
        """Run offline schema alignment checks.

        Args:
            schema: Schema definition to validate.
            session: Ignored (offline check).

        Returns:
            CheckResult with PASSED, WARNING, or FAILED status.
        """
        issues: list[str] = []

        for label, label_schema in schema.labels.items():
            # Empty label names
            if not label.strip():
                issues.append("Empty or whitespace-only label name found")
                continue

            defined = set(label_schema.properties.keys())

            # Required properties must be a subset of defined properties
            undefined_required = label_schema.required_properties - defined
            if undefined_required:
                issues.append(
                    f"Label '{label}': required properties not in schema: "
                    f"{sorted(undefined_required)}"
                )

            # Enum value sets must be non-empty when specified
            for prop_name, prop_schema in label_schema.properties.items():
                if prop_schema.enum_values is not None and len(prop_schema.enum_values) == 0:
                    issues.append(
                        f"Label '{label}', property '{prop_name}': "
                        "enum_values is specified but empty"
                    )

                # Cardinality sanity
                if prop_schema.min_cardinality < 0:
                    issues.append(
                        f"Label '{label}', property '{prop_name}': "
                        "min_cardinality is negative"
                    )
                if (
                    prop_schema.max_cardinality is not None
                    and prop_schema.max_cardinality < prop_schema.min_cardinality
                ):
                    issues.append(
                        f"Label '{label}', property '{prop_name}': "
                        "max_cardinality < min_cardinality"
                    )

        if issues:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAILED,
                message=f"Schema definition has {len(issues)} structural issue(s)",
                details={"issues": issues},
            )

        return CheckResult(
            name=self.name,
            status=CheckStatus.PASSED,
            message=(
                f"Schema definition is valid: {len(schema.labels)} label(s), "
                f"{len(schema.relationship_types)} relationship type(s)"
            ),
            details={
                "label_count": len(schema.labels),
                "relationship_type_count": len(schema.relationship_types),
            },
        )


# ---------------------------------------------------------------------------
# 2. PropertyTypeCheck (online)
# ---------------------------------------------------------------------------

# Mapping from schema type name to Neo4j / Python type predicates used in
# Cypher.  Each tuple holds (cypher_type_fn, display_name).
_TYPE_PREDICATES: dict[str, str] = {
    "str": "apoc.meta.type(n.`{prop}`) = 'STRING'",
    "int": "apoc.meta.type(n.`{prop}`) = 'INTEGER'",
    "float": "apoc.meta.type(n.`{prop}`) IN ['FLOAT', 'DOUBLE']",
    "bool": "apoc.meta.type(n.`{prop}`) = 'BOOLEAN'",
    "datetime": "apoc.meta.type(n.`{prop}`) IN ['DATE', 'DATE_TIME', 'LOCAL_DATE_TIME']",
    "list": "apoc.meta.type(n.`{prop}`) IN ['LIST', 'ARRAY']",
    "point": "apoc.meta.type(n.`{prop}`) = 'POINT'",
}


class PropertyTypeCheck(ConsistencyCheck):
    """Validates that node properties match expected types defined in the schema.

    For each (label, property) pair in the schema, executes a Cypher query
    using ``apoc.meta.type`` to count nodes whose property value does not
    match the expected type.  Requires APOC plugin in Neo4j.
    """

    @property
    def name(self) -> str:  # noqa: D102
        return "property_type"

    @property
    def description(self) -> str:  # noqa: D102
        return (
            "Validates that node properties match expected types "
            "from the schema using apoc.meta.type."
        )

    @property
    def requires_connection(self) -> bool:  # noqa: D102
        return True

    def check(
        self,
        schema: SchemaDefinition,
        session: Any | None = None,
    ) -> CheckResult:
        """Run property type validation against live Neo4j.

        Args:
            schema: Schema definition containing expected property types.
            session: Open Neo4j session.  Returns SKIPPED if None.

        Returns:
            CheckResult with PASSED, FAILED, or SKIPPED status.
        """
        if session is None:
            return CheckResult(
                name=self.name,
                status=CheckStatus.SKIPPED,
                message="Property type check requires a live Neo4j connection",
                details={"reason": "no_neo4j"},
            )

        violations: list[dict[str, Any]] = []

        try:
            for label, label_schema in schema.labels.items():
                for prop_name, prop_schema in label_schema.properties.items():
                    predicate_template = _TYPE_PREDICATES.get(prop_schema.expected_type)
                    if predicate_template is None:
                        logger.warning(
                            "Unknown expected_type '%s' for %s.%s — skipping",
                            prop_schema.expected_type,
                            label,
                            prop_name,
                        )
                        continue

                    predicate = predicate_template.format(prop=prop_name)
                    cypher = (
                        f"MATCH (n:`{label}`) "
                        f"WHERE n.`{prop_name}` IS NOT NULL "
                        f"AND NOT ({predicate}) "
                        f"RETURN count(n) AS bad_count"
                    )
                    result = session.run(cypher)
                    record = result.single()
                    bad_count = record["bad_count"] if record else 0

                    if bad_count > 0:
                        violations.append(
                            {
                                "label": label,
                                "property": prop_name,
                                "expected_type": prop_schema.expected_type,
                                "bad_count": bad_count,
                            }
                        )

        except Exception as exc:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAILED,
                message=f"Property type check error: {exc}",
                details={"error": str(exc)},
            )

        if violations:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAILED,
                message=(
                    f"Property type violations found in {len(violations)} (label, property) pair(s)"
                ),
                details={"violations": violations},
            )

        return CheckResult(
            name=self.name,
            status=CheckStatus.PASSED,
            message="All node properties match their expected types",
            details={"checked_pairs": sum(len(ls.properties) for ls in schema.labels.values())},
        )


# ---------------------------------------------------------------------------
# 3. RequiredPropertyCheck (online)
# ---------------------------------------------------------------------------


class RequiredPropertyCheck(ConsistencyCheck):
    """Validates that required properties are present on all nodes of each label.

    For each required property, runs:
    ``MATCH (n:Label) WHERE n.prop IS NULL RETURN count(n)``
    and fails if any nodes are missing the property.
    """

    @property
    def name(self) -> str:  # noqa: D102
        return "required_property"

    @property
    def description(self) -> str:  # noqa: D102
        return (
            "Validates that required properties are present on all "
            "nodes of each label."
        )

    @property
    def requires_connection(self) -> bool:  # noqa: D102
        return True

    def check(
        self,
        schema: SchemaDefinition,
        session: Any | None = None,
    ) -> CheckResult:
        """Run required-property validation against live Neo4j.

        Args:
            schema: Schema definition with required_properties per label.
            session: Open Neo4j session.  Returns SKIPPED if None.

        Returns:
            CheckResult with PASSED, FAILED, or SKIPPED status.
        """
        if session is None:
            return CheckResult(
                name=self.name,
                status=CheckStatus.SKIPPED,
                message="Required property check requires a live Neo4j connection",
                details={"reason": "no_neo4j"},
            )

        missing_entries: list[dict[str, Any]] = []

        try:
            for label, label_schema in schema.labels.items():
                for prop_name in label_schema.required_properties:
                    cypher = (
                        f"MATCH (n:`{label}`) "
                        f"WHERE n.`{prop_name}` IS NULL "
                        f"RETURN count(n) AS missing_count"
                    )
                    result = session.run(cypher)
                    record = result.single()
                    missing_count = record["missing_count"] if record else 0

                    if missing_count > 0:
                        missing_entries.append(
                            {
                                "label": label,
                                "property": prop_name,
                                "missing_count": missing_count,
                            }
                        )

        except Exception as exc:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAILED,
                message=f"Required property check error: {exc}",
                details={"error": str(exc)},
            )

        if missing_entries:
            total_missing = sum(e["missing_count"] for e in missing_entries)
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAILED,
                message=(
                    f"{total_missing} node(s) missing required properties across "
                    f"{len(missing_entries)} (label, property) pair(s)"
                ),
                details={"missing_entries": missing_entries},
            )

        return CheckResult(
            name=self.name,
            status=CheckStatus.PASSED,
            message="All required properties are present on their respective nodes",
            details={
                "checked_pairs": sum(
                    len(ls.required_properties) for ls in schema.labels.values()
                )
            },
        )


# ---------------------------------------------------------------------------
# 4. EnumValueCheck (online)
# ---------------------------------------------------------------------------


class EnumValueCheck(ConsistencyCheck):
    """Validates that enum-constrained property values are within allowed sets.

    For each property with ``enum_values`` defined, runs:
    ``MATCH (n:Label) WHERE n.prop IS NOT NULL AND NOT n.prop IN $allowed``
    and fails if any out-of-range values are found.
    """

    @property
    def name(self) -> str:  # noqa: D102
        return "enum_value"

    @property
    def description(self) -> str:  # noqa: D102
        return (
            "Validates that enum-constrained property values are within "
            "the allowed value sets defined in the schema."
        )

    @property
    def requires_connection(self) -> bool:  # noqa: D102
        return True

    def check(
        self,
        schema: SchemaDefinition,
        session: Any | None = None,
    ) -> CheckResult:
        """Run enum value validation against live Neo4j.

        Args:
            schema: Schema definition with enum_values per property.
            session: Open Neo4j session.  Returns SKIPPED if None.

        Returns:
            CheckResult with PASSED, FAILED, or SKIPPED status.
        """
        if session is None:
            return CheckResult(
                name=self.name,
                status=CheckStatus.SKIPPED,
                message="Enum value check requires a live Neo4j connection",
                details={"reason": "no_neo4j"},
            )

        violations: list[dict[str, Any]] = []

        try:
            for label, label_schema in schema.labels.items():
                for prop_name, prop_schema in label_schema.properties.items():
                    if prop_schema.enum_values is None:
                        continue

                    allowed = list(prop_schema.enum_values)
                    cypher = (
                        f"MATCH (n:`{label}`) "
                        f"WHERE n.`{prop_name}` IS NOT NULL "
                        f"AND NOT n.`{prop_name}` IN $allowed "
                        f"RETURN count(n) AS bad_count, "
                        f"collect(DISTINCT n.`{prop_name}`)[..5] AS sample_bad"
                    )
                    result = session.run(cypher, allowed=allowed)
                    record = result.single()
                    bad_count = record["bad_count"] if record else 0
                    sample_bad = record["sample_bad"] if record else []

                    if bad_count > 0:
                        violations.append(
                            {
                                "label": label,
                                "property": prop_name,
                                "allowed_values": allowed,
                                "bad_count": bad_count,
                                "sample_bad_values": sample_bad,
                            }
                        )

        except Exception as exc:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAILED,
                message=f"Enum value check error: {exc}",
                details={"error": str(exc)},
            )

        if violations:
            total_bad = sum(v["bad_count"] for v in violations)
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAILED,
                message=(
                    f"{total_bad} node(s) with out-of-range enum values across "
                    f"{len(violations)} (label, property) pair(s)"
                ),
                details={"violations": violations},
            )

        return CheckResult(
            name=self.name,
            status=CheckStatus.PASSED,
            message="All enum-constrained properties have valid values",
            details={
                "checked_pairs": sum(
                    1
                    for ls in schema.labels.values()
                    for ps in ls.properties.values()
                    if ps.enum_values is not None
                )
            },
        )


# ---------------------------------------------------------------------------
# 5. CardinalityCheck (online)
# ---------------------------------------------------------------------------


class CardinalityCheck(ConsistencyCheck):
    """Validates relationship cardinality constraints defined in the schema.

    For each label, checks that the count of outgoing relationships per node
    falls within [min_cardinality, max_cardinality] as defined on the label's
    ``PropertySchema``.  When ``max_cardinality`` is ``None`` only the
    minimum is enforced.

    Note:
        This check uses property cardinality constraints (how many times a
        property may appear / how many relationships are expected) rather than
        per-relationship-type cardinality, which is not yet expressed in
        ``PropertySchema``.  The current implementation checks the total
        degree of each node per label against the aggregate min/max.
    """

    @property
    def name(self) -> str:  # noqa: D102
        return "cardinality"

    @property
    def description(self) -> str:  # noqa: D102
        return (
            "Validates relationship cardinality: checks that node degree "
            "satisfies min/max_cardinality constraints from the schema."
        )

    @property
    def requires_connection(self) -> bool:  # noqa: D102
        return True

    def check(
        self,
        schema: SchemaDefinition,
        session: Any | None = None,
    ) -> CheckResult:
        """Run cardinality validation against live Neo4j.

        Args:
            schema: Schema definition with cardinality constraints.
            session: Open Neo4j session.  Returns SKIPPED if None.

        Returns:
            CheckResult with PASSED, FAILED, WARNING, or SKIPPED status.
        """
        if session is None:
            return CheckResult(
                name=self.name,
                status=CheckStatus.SKIPPED,
                message="Cardinality check requires a live Neo4j connection",
                details={"reason": "no_neo4j"},
            )

        # Collect labels that define explicit min or max cardinality
        constrained_labels: list[tuple[str, int, int | None]] = []
        for label, label_schema in schema.labels.items():
            # Aggregate constraints across all properties on this label
            # Use the most restrictive (highest min, lowest max)
            min_card = max(
                (ps.min_cardinality for ps in label_schema.properties.values()),
                default=0,
            )
            max_cards = [
                ps.max_cardinality
                for ps in label_schema.properties.values()
                if ps.max_cardinality is not None
            ]
            max_card: int | None = min(max_cards) if max_cards else None

            if min_card > 0 or max_card is not None:
                constrained_labels.append((label, min_card, max_card))

        if not constrained_labels:
            return CheckResult(
                name=self.name,
                status=CheckStatus.SKIPPED,
                message="No cardinality constraints defined in schema",
                details={"reason": "no_constraints"},
            )

        violations: list[dict[str, Any]] = []

        try:
            for label, min_card, max_card in constrained_labels:
                # Nodes below minimum degree
                if min_card > 0:
                    cypher_min = (
                        f"MATCH (n:`{label}`) "
                        f"WITH n, size([(n)--() | 1]) AS deg "
                        f"WHERE deg < $min_card "
                        f"RETURN count(n) AS bad_count"
                    )
                    result = session.run(cypher_min, min_card=min_card)
                    record = result.single()
                    bad_count = record["bad_count"] if record else 0
                    if bad_count > 0:
                        violations.append(
                            {
                                "label": label,
                                "constraint": f"degree >= {min_card}",
                                "bad_count": bad_count,
                            }
                        )

                # Nodes above maximum degree
                if max_card is not None:
                    cypher_max = (
                        f"MATCH (n:`{label}`) "
                        f"WITH n, size([(n)--() | 1]) AS deg "
                        f"WHERE deg > $max_card "
                        f"RETURN count(n) AS bad_count"
                    )
                    result = session.run(cypher_max, max_card=max_card)
                    record = result.single()
                    bad_count = record["bad_count"] if record else 0
                    if bad_count > 0:
                        violations.append(
                            {
                                "label": label,
                                "constraint": f"degree <= {max_card}",
                                "bad_count": bad_count,
                            }
                        )

        except Exception as exc:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAILED,
                message=f"Cardinality check error: {exc}",
                details={"error": str(exc)},
            )

        if violations:
            total_bad = sum(v["bad_count"] for v in violations)
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAILED,
                message=(
                    f"{total_bad} node(s) violate cardinality constraints "
                    f"across {len(violations)} label(s)"
                ),
                details={"violations": violations},
            )

        return CheckResult(
            name=self.name,
            status=CheckStatus.PASSED,
            message=(
                f"Cardinality constraints satisfied for {len(constrained_labels)} label(s)"
            ),
            details={"constrained_labels": [lbl for lbl, _, _ in constrained_labels]},
        )


# ---------------------------------------------------------------------------
# 6. OrphanNodeCheck (online)
# ---------------------------------------------------------------------------


class OrphanNodeCheck(ConsistencyCheck):
    """Finds nodes that have no relationships whatsoever.

    Orphan nodes are often the result of incomplete data loading or
    failed ingestion pipelines.  A high orphan rate indicates data quality
    issues.
    """

    @property
    def name(self) -> str:  # noqa: D102
        return "orphan_node"

    @property
    def description(self) -> str:  # noqa: D102
        return (
            "Finds nodes with no relationships.  High orphan rates indicate "
            "incomplete ingestion or broken references."
        )

    @property
    def requires_connection(self) -> bool:  # noqa: D102
        return True

    def check(
        self,
        schema: SchemaDefinition,
        session: Any | None = None,
    ) -> CheckResult:
        """Find orphan nodes per label in live Neo4j.

        Args:
            schema: Schema definition (used to scope which labels to check).
            session: Open Neo4j session.  Returns SKIPPED if None.

        Returns:
            CheckResult with PASSED (no orphans), WARNING (some orphans), or
            SKIPPED status.
        """
        if session is None:
            return CheckResult(
                name=self.name,
                status=CheckStatus.SKIPPED,
                message="Orphan node check requires a live Neo4j connection",
                details={"reason": "no_neo4j"},
            )

        orphan_summary: list[dict[str, Any]] = []
        total_orphans = 0

        try:
            labels_to_check = list(schema.labels.keys()) if schema.labels else []

            if not labels_to_check:
                # Check all labels if schema has none defined
                cypher_all = (
                    "MATCH (n) WHERE NOT (n)--() "
                    "RETURN labels(n) AS node_labels, count(n) AS orphan_count"
                )
                result = session.run(cypher_all)
                for record in result:
                    count = record["orphan_count"]
                    total_orphans += count
                    orphan_summary.append(
                        {
                            "labels": record["node_labels"],
                            "orphan_count": count,
                        }
                    )
            else:
                for label in labels_to_check:
                    cypher = (
                        f"MATCH (n:`{label}`) WHERE NOT (n)--() "
                        f"RETURN count(n) AS orphan_count"
                    )
                    result = session.run(cypher)
                    record = result.single()
                    count = record["orphan_count"] if record else 0
                    if count > 0:
                        total_orphans += count
                        orphan_summary.append({"label": label, "orphan_count": count})

        except Exception as exc:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAILED,
                message=f"Orphan node check error: {exc}",
                details={"error": str(exc)},
            )

        if total_orphans > 0:
            return CheckResult(
                name=self.name,
                status=CheckStatus.WARNING,
                message=f"{total_orphans} orphan node(s) found with no relationships",
                details={"total_orphans": total_orphans, "by_label": orphan_summary},
            )

        return CheckResult(
            name=self.name,
            status=CheckStatus.PASSED,
            message="No orphan nodes found",
            details={"total_orphans": 0},
        )


# ---------------------------------------------------------------------------
# 7. DanglingRelationshipCheck (online)
# ---------------------------------------------------------------------------


class DanglingRelationshipCheck(ConsistencyCheck):
    """Finds relationships whose endpoint nodes have unexpected labels.

    A dangling relationship is one where either the start or end node carries
    a label not present in ``schema.labels``.  This indicates stale or
    inconsistent data.
    """

    @property
    def name(self) -> str:  # noqa: D102
        return "dangling_relationship"

    @property
    def description(self) -> str:  # noqa: D102
        return (
            "Finds relationships referencing nodes with labels not defined "
            "in the schema (unexpected endpoint labels)."
        )

    @property
    def requires_connection(self) -> bool:  # noqa: D102
        return True

    def check(
        self,
        schema: SchemaDefinition,
        session: Any | None = None,
    ) -> CheckResult:
        """Find dangling relationships in live Neo4j.

        Args:
            schema: Schema definition with known labels and relationship types.
            session: Open Neo4j session.  Returns SKIPPED if None.

        Returns:
            CheckResult with PASSED, WARNING, or SKIPPED status.
        """
        if session is None:
            return CheckResult(
                name=self.name,
                status=CheckStatus.SKIPPED,
                message="Dangling relationship check requires a live Neo4j connection",
                details={"reason": "no_neo4j"},
            )

        known_labels = set(schema.labels.keys())

        if not known_labels:
            return CheckResult(
                name=self.name,
                status=CheckStatus.SKIPPED,
                message="No labels defined in schema; cannot check for dangling relationships",
                details={"reason": "no_labels_in_schema"},
            )

        dangling: list[dict[str, Any]] = []

        try:
            cypher = (
                "MATCH (a)-[r]->(b) "
                "WITH type(r) AS rel_type, "
                "     labels(a) AS start_labels, "
                "     labels(b) AS end_labels, "
                "     count(*) AS rel_count "
                "RETURN rel_type, start_labels, end_labels, rel_count "
                "ORDER BY rel_count DESC "
                "LIMIT 500"
            )
            result = session.run(cypher)

            for record in result:
                start_labels: list[str] = record["start_labels"]
                end_labels: list[str] = record["end_labels"]

                # Check if any endpoint label is completely outside known labels
                start_unknown = [lbl for lbl in start_labels if lbl not in known_labels]
                end_unknown = [lbl for lbl in end_labels if lbl not in known_labels]

                if start_unknown or end_unknown:
                    dangling.append(
                        {
                            "relationship_type": record["rel_type"],
                            "start_labels": start_labels,
                            "end_labels": end_labels,
                            "unknown_start_labels": start_unknown,
                            "unknown_end_labels": end_unknown,
                            "relationship_count": record["rel_count"],
                        }
                    )

        except Exception as exc:
            return CheckResult(
                name=self.name,
                status=CheckStatus.FAILED,
                message=f"Dangling relationship check error: {exc}",
                details={"error": str(exc)},
            )

        if dangling:
            total_rels = sum(d["relationship_count"] for d in dangling)
            return CheckResult(
                name=self.name,
                status=CheckStatus.WARNING,
                message=(
                    f"{total_rels} relationship(s) across {len(dangling)} type/endpoint "
                    "combination(s) reference unexpected labels"
                ),
                details={
                    "dangling_count": len(dangling),
                    "total_relationships": total_rels,
                    "dangling": dangling[:20],
                    "known_labels": sorted(known_labels),
                },
            )

        return CheckResult(
            name=self.name,
            status=CheckStatus.PASSED,
            message="No dangling relationships found; all endpoints use known labels",
            details={"known_labels": sorted(known_labels)},
        )
