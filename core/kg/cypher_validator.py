"""Cypher query validation for the Text-to-Cypher pipeline.

Validates generated Cypher queries against ontology schema and basic syntax
rules.  This is Stage 3 (Validate) of the 4-stage pipeline:
Parse -> Generate -> **Validate** -> Correct.

Usage::

    from kg.cypher_validator import CypherValidator, FailureType

    validator = CypherValidator.from_maritime_ontology()
    result = validator.validate("MATCH (v:Vessel) RETURN v")
    assert result.is_valid
    assert result.failure_type == FailureType.NONE
"""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FailureType(str, Enum):
    """GraphRAG failure type classification (Part 11).

    Three categories for rapid debugging:

    - ``SCHEMA``: Cypher 문법/스키마 오류 (syntax errors, invalid labels/rels).
    - ``RETRIEVAL``: 검색 실패 (노드 미발견, 빈 결과).
    - ``GENERATION``: 생성 실패 (답변 품질 문제).
    - ``NONE``: 정상 -- no failure detected.

    Members:
        NONE: No failure -- query is valid.
        SCHEMA: Cypher syntax error, invalid labels, or invalid relationship
            types.  Typically fixable by the corrector stage.
        RETRIEVAL: Empty results or node not found.  The query is
            syntactically correct but unlikely to return data (e.g., references
            non-existent properties).
        GENERATION: Answer quality issue.  The generated Cypher does not
            semantically match the user intent.
    """

    NONE = "none"
    SCHEMA = "schema"
    RETRIEVAL = "retrieval"
    GENERATION = "generation"


@dataclass
class ValidationResult:
    """Result of Cypher query validation.

    Attributes:
        is_valid: Whether the query passed all validation checks.
        errors: Critical issues that make the query incorrect.
        warnings: Non-critical issues (query may still execute).
        score: Quality score from 0.0 (invalid) to 1.0 (perfect).
        failure_type: GraphRAG Part 11 failure classification.
    """

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    score: float = 1.0
    failure_type: FailureType = FailureType.NONE


# Regex patterns for extracting Cypher constructs
# Matches node patterns like (v:Label) or (:Label)
_LABEL_PATTERN = re.compile(r"\(\s*\w*\s*:\s*([A-Za-z_]\w*)\s*\)")
# Matches relationship patterns like [:REL_TYPE] or [r:REL_TYPE]
_REL_PATTERN = re.compile(r"\[\s*\w*\s*:\s*([A-Za-z_]\w*)\s*\]")
# Matches RETURN clause (case-insensitive)
_RETURN_PATTERN = re.compile(r"\bRETURN\b", re.IGNORECASE)
# Matches MATCH clause (case-insensitive)
_MATCH_PATTERN = re.compile(r"\bMATCH\b", re.IGNORECASE)


class CypherValidator:
    """Validates generated Cypher queries against ontology and syntax rules.

    Performs 6 validation checks:

    1. Basic syntax validation (MATCH/RETURN pattern)
    2. Node label existence in ontology
    3. Relationship type existence in ontology
    4. Property name verification (best-effort via ontology)
    5. Relationship direction check (based on ontology constraints)
    6. Return clause presence

    Args:
        ontology: Optional Ontology instance for semantic validation.
            When ``None``, only syntax checks are performed.
    """

    def __init__(self, ontology: Any | None = None) -> None:
        """Initialize with optional ontology for semantic validation."""
        self._ontology = ontology
        self._valid_labels: set[str] = set()
        self._valid_rel_types: set[str] = set()
        self._valid_properties: dict[str, set[str]] = {}

        if ontology is not None:
            self._extract_ontology_schema(ontology)

    @classmethod
    def from_maritime_ontology(cls) -> CypherValidator:
        """Create a validator pre-loaded with the maritime ontology.

        .. deprecated::
            Use ``kg.maritime_factories.create_maritime_validator()`` instead.
            This method will be removed in the next major version.

        Returns:
            CypherValidator with all maritime labels and relationship types.
        """
        warnings.warn(
            "from_maritime_ontology() is deprecated. "
            "Use kg.maritime_factories.create_maritime_validator() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        from maritime.ontology.maritime_loader import load_maritime_ontology

        return cls(ontology=load_maritime_ontology())

    @classmethod
    def from_labels_and_types(
        cls,
        labels: set[str],
        rel_types: set[str],
    ) -> CypherValidator:
        """Create a validator from explicit label/relationship sets.

        Useful for testing without loading the full ontology.

        Args:
            labels: Set of valid node labels.
            rel_types: Set of valid relationship types.

        Returns:
            CypherValidator with the provided schema.
        """
        instance = cls(ontology=None)
        instance._valid_labels = set(labels)
        instance._valid_rel_types = set(rel_types)
        return instance

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate(self, cypher: str) -> ValidationResult:
        """Run all validation checks on a Cypher query.

        Args:
            cypher: The Cypher query string to validate.

        Returns:
            ValidationResult with errors, warnings, and a quality score.
        """
        if not cypher or not cypher.strip():
            return ValidationResult(
                is_valid=False,
                errors=["Empty query"],
                score=0.0,
                failure_type=FailureType.SCHEMA,
            )

        errors: list[str] = []
        warnings: list[str] = []

        # 1. Syntax check
        errors.extend(self._check_syntax(cypher))

        # 2. Label check (only if ontology-aware)
        if self._valid_labels:
            label_errors, label_warnings = self._check_labels(cypher)
            errors.extend(label_errors)
            warnings.extend(label_warnings)

        # 3. Relationship type check (only if ontology-aware)
        if self._valid_rel_types:
            rel_errors, rel_warnings = self._check_relationships(cypher)
            errors.extend(rel_errors)
            warnings.extend(rel_warnings)

        # 4. Property check (best-effort)
        if self._valid_properties:
            prop_warnings = self._check_properties(cypher)
            warnings.extend(prop_warnings)

        # 5. Relationship direction check
        if self._ontology is not None:
            dir_warnings = self._check_relationship_directions(cypher)
            warnings.extend(dir_warnings)

        # 6. RETURN clause check
        errors.extend(self._check_return_clause(cypher))

        # Compute score and classify failure
        score = self._compute_score(errors, warnings)
        is_valid = len(errors) == 0
        failure_type = self.classify_failure_type(errors, warnings)

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            score=score,
            failure_type=failure_type,
        )

    # ------------------------------------------------------------------
    # Failure classification
    # ------------------------------------------------------------------

    @staticmethod
    def classify_failure_type(
        errors: list[str],
        warnings: list[str],
    ) -> FailureType:
        """Classify the failure type based on validation errors and warnings.

        Implements GraphRAG Part 11 failure classification for rapid
        debugging and pipeline analytics.

        Classification rules (evaluated in order):

        1. If *errors* contain syntax-related messages (missing MATCH,
           missing RETURN, unknown labels, unknown relationship types),
           return ``SCHEMA``.
        2. If no errors but *warnings* reference missing properties,
           return ``RETRIEVAL`` (query is syntactically valid but unlikely
           to find matching nodes).
        3. Otherwise return ``NONE`` (valid query).

        Args:
            errors: Error messages from validation.
            warnings: Warning messages from validation.

        Returns:
            The classified FailureType.
        """
        if errors:
            # All current validator errors are schema-level issues:
            # "Missing MATCH clause", "Missing RETURN clause",
            # "Unknown node label '...'", "Unknown relationship type '...'"
            return FailureType.SCHEMA

        # No errors -- check warnings for retrieval-risk indicators
        if warnings:
            for warning in warnings:
                if "may not exist" in warning:
                    return FailureType.RETRIEVAL

        return FailureType.NONE

    # ------------------------------------------------------------------
    # Validation checks
    # ------------------------------------------------------------------

    def _check_syntax(self, cypher: str) -> list[str]:
        """Check basic Cypher syntax patterns.

        Validates that the query contains a MATCH clause (the most
        fundamental read pattern).

        Args:
            cypher: Cypher query string.

        Returns:
            List of syntax error messages (may be empty).
        """
        errors: list[str] = []

        if not _MATCH_PATTERN.search(cypher):
            errors.append("Missing MATCH clause")

        return errors

    def _check_labels(self, cypher: str) -> tuple[list[str], list[str]]:
        """Check that node labels exist in ontology.

        Extracts ``:Label`` patterns from node expressions and verifies
        each against the known ontology labels.

        Args:
            cypher: Cypher query string.

        Returns:
            Tuple of (errors, warnings).
        """
        errors: list[str] = []
        warnings: list[str] = []

        labels_found = _LABEL_PATTERN.findall(cypher)
        for label in labels_found:
            if label == "Node":
                # Generic placeholder, skip
                continue
            if label not in self._valid_labels:
                # Check for case-insensitive match (common mistake)
                lower_map = {v.lower(): v for v in self._valid_labels}
                if label.lower() in lower_map:
                    correct = lower_map[label.lower()]
                    warnings.append(
                        f"Label '{label}' has wrong case; "
                        f"did you mean '{correct}'?"
                    )
                else:
                    errors.append(
                        f"Unknown node label '{label}' "
                        f"(not in ontology)"
                    )

        return errors, warnings

    def _check_relationships(self, cypher: str) -> tuple[list[str], list[str]]:
        """Check that relationship types exist in ontology.

        Extracts ``[:REL_TYPE]`` patterns and verifies each against the
        known ontology relationship types.

        Args:
            cypher: Cypher query string.

        Returns:
            Tuple of (errors, warnings).
        """
        errors: list[str] = []
        warnings: list[str] = []

        rel_types_found = _REL_PATTERN.findall(cypher)
        for rel_type in rel_types_found:
            if rel_type not in self._valid_rel_types:
                # Check for case-insensitive match
                upper_map = {v.upper(): v for v in self._valid_rel_types}
                if rel_type.upper() in upper_map:
                    correct = upper_map[rel_type.upper()]
                    if rel_type != correct:
                        warnings.append(
                            f"Relationship type '{rel_type}' has wrong case; "
                            f"did you mean '{correct}'?"
                        )
                else:
                    errors.append(
                        f"Unknown relationship type '{rel_type}' "
                        f"(not in ontology)"
                    )

        return errors, warnings

    def _check_properties(self, cypher: str) -> list[str]:
        """Check property names against ontology definitions.

        Best-effort check: extracts ``alias.propertyName`` patterns and
        verifies against known properties for the labels used in the query.

        Args:
            cypher: Cypher query string.

        Returns:
            List of warning messages.
        """
        warnings: list[str] = []

        # Find all labels used in the query to know which properties to check
        labels_in_query = set(_LABEL_PATTERN.findall(cypher))

        # Collect all known properties for these labels
        known_props: set[str] = set()
        for label in labels_in_query:
            if label in self._valid_properties:
                known_props.update(self._valid_properties[label])

        # If no properties are known for these labels, skip
        if not known_props:
            return warnings

        # Extract property references like alias.propName in WHERE/RETURN
        prop_refs = re.findall(r"\b\w+\.(\w+)\b", cypher)
        for prop in prop_refs:
            # Skip Cypher keywords/aggregation functions
            if prop.upper() in ("COUNT", "SUM", "AVG", "MIN", "MAX", "AS"):
                continue
            if prop not in known_props:
                warnings.append(
                    f"Property '{prop}' may not exist on queried labels"
                )

        return warnings

    def _check_relationship_directions(self, cypher: str) -> list[str]:
        """Check relationship directions against ontology constraints.

        Verifies that relationships are used in the correct direction
        (from_type -> to_type) as defined in the ontology.

        Args:
            cypher: Cypher query string.

        Returns:
            List of warning messages.
        """
        warnings: list[str] = []

        if self._ontology is None:
            return warnings

        # Extract directional relationship patterns:
        # (a:LabelA)-[:REL]->(b:LabelB) or (a:LabelA)<-[:REL]-(b:LabelB)
        outgoing = re.findall(
            r"\(\s*\w*\s*:\s*(\w+)\s*\)\s*-\s*\[\s*\w*\s*:\s*(\w+)\s*\]\s*->\s*\(\s*\w*\s*:\s*(\w+)\s*\)",
            cypher,
        )
        for from_label, rel_type, to_label in outgoing:
            link = self._ontology.get_link_type(rel_type)
            if link is not None:
                if link.from_type != from_label or link.to_type != to_label:
                    warnings.append(
                        f"Relationship {rel_type} is defined as "
                        f"({link.from_type})->({link.to_type}), "
                        f"but used as ({from_label})->({to_label})"
                    )

        return warnings

    def _check_return_clause(self, cypher: str) -> list[str]:
        """Verify RETURN clause is present and non-empty.

        Args:
            cypher: Cypher query string.

        Returns:
            List of error messages.
        """
        errors: list[str] = []

        if not _RETURN_PATTERN.search(cypher):
            errors.append("Missing RETURN clause")

        return errors

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_ontology_schema(self, ontology: Any) -> None:
        """Extract valid labels, relationship types, and properties from ontology.

        Args:
            ontology: An Ontology instance with object_types and link_types.
        """
        # Extract node labels
        for obj_type in ontology.get_all_object_types():
            self._valid_labels.add(obj_type.name)
            # Collect properties per label
            if obj_type.properties:
                self._valid_properties[obj_type.name] = set(
                    obj_type.properties.keys()
                )

        # Extract relationship types
        for link_type in ontology.get_all_link_types():
            self._valid_rel_types.add(link_type.name)

    def _compute_score(self, errors: list[str], warnings: list[str]) -> float:
        """Compute a quality score based on errors and warnings.

        Scoring:
        - Starts at 1.0
        - Each error deducts 0.3 (capped at 0.0)
        - Each warning deducts 0.1 (minimum 0.1 if no errors)

        Args:
            errors: List of error messages.
            warnings: List of warning messages.

        Returns:
            Float score between 0.0 and 1.0.
        """
        if errors:
            score = max(0.0, 1.0 - len(errors) * 0.3 - len(warnings) * 0.1)
            return round(score, 2)

        score = max(0.1, 1.0 - len(warnings) * 0.1)
        return round(score, 2)
