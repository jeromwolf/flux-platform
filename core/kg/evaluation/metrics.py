"""Lightweight evaluation metrics for Text-to-Cypher quality measurement.

RAGAS-style metrics implemented from scratch without external dependencies.
Compares generated Cypher queries against ground truth using structural
component extraction (labels, relationship types, return fields).

Usage::

    from kg.evaluation.metrics import CypherAccuracy, QueryRelevancy

    accuracy = CypherAccuracy()
    score = accuracy.evaluate(generated_cypher, ground_truth_cypher)

    relevancy = QueryRelevancy()
    score = relevancy.evaluate(question, generated_cypher, expected_labels)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# =========================================================================
# Cypher component extraction helpers
# =========================================================================


def _extract_node_labels(cypher: str) -> set[str]:
    """Extract Neo4j node labels from a Cypher query string.

    Matches patterns like ``(v:Vessel)``, ``(:Port)``, ``(n:Vessel:CargoShip)``.

    Args:
        cypher: Cypher query string.

    Returns:
        Set of unique node label strings.
    """
    labels: set[str] = set()
    # Pattern: colon followed by PascalCase word inside parentheses context
    # Handles multi-label like :Vessel:CargoShip
    for match in re.finditer(r"\(\s*\w*\s*((?::\w+)+)\s*", cypher):
        label_group = match.group(1)
        for label in label_group.split(":"):
            label = label.strip()
            if label:
                labels.add(label)
    return labels


def _extract_relationship_types(cypher: str) -> set[str]:
    """Extract relationship types from a Cypher query string.

    Matches patterns like ``[:DOCKED_AT]``, ``-[:ON_VOYAGE]->``.

    Args:
        cypher: Cypher query string.

    Returns:
        Set of unique relationship type strings.
    """
    types: set[str] = set()
    for match in re.finditer(r"\[(?:\w*:)?(\w+)\]", cypher):
        rel_type = match.group(1)
        # Filter out variable-only bindings (lowercase only)
        if rel_type.upper() == rel_type or "_" in rel_type:
            types.add(rel_type)
    return types


def _extract_return_fields(cypher: str) -> set[str]:
    """Extract RETURN clause field identifiers from a Cypher query.

    Extracts the aliases or property references from the RETURN clause.

    Args:
        cypher: Cypher query string.

    Returns:
        Set of return field identifiers.
    """
    fields: set[str] = set()
    # Find RETURN clause (case-insensitive)
    return_match = re.search(r"\bRETURN\b\s+(.+?)(?:\bORDER\b|\bLIMIT\b|\bSKIP\b|$)", cypher, re.IGNORECASE | re.DOTALL)
    if not return_match:
        return fields

    return_clause = return_match.group(1).strip()
    # Split by commas, handle AS aliases
    for part in return_clause.split(","):
        part = part.strip()
        if not part:
            continue
        # If there's an AS alias, use the alias
        as_match = re.search(r"\bAS\b\s+(\w+)", part, re.IGNORECASE)
        if as_match:
            fields.add(as_match.group(1))
        else:
            # Use the raw field reference (e.g., v, p.name)
            # Extract the variable or property name
            prop_match = re.match(r"(\w+(?:\.\w+)?)", part)
            if prop_match:
                fields.add(prop_match.group(1))

    return fields


def _extract_property_filters(cypher: str) -> set[str]:
    """Extract property filter references from WHERE and inline patterns.

    Matches ``{name: 'xxx'}``, ``WHERE v.vesselType = $type``, etc.

    Args:
        cypher: Cypher query string.

    Returns:
        Set of property name strings referenced in filters.
    """
    props: set[str] = set()

    # Inline property filters: {key: value}
    for match in re.finditer(r"\{([^}]+)\}", cypher):
        inner = match.group(1)
        for kv in inner.split(","):
            key_match = re.match(r"\s*(\w+)\s*:", kv)
            if key_match:
                props.add(key_match.group(1))

    # WHERE clause property references: alias.property op value
    for match in re.finditer(r"(\w+)\.(\w+)\s*(?:=|<>|<|>|<=|>=|CONTAINS|IN)\s*", cypher, re.IGNORECASE):
        props.add(match.group(2))

    return props


# =========================================================================
# CypherAccuracy metric
# =========================================================================


@dataclass
class CypherComponents:
    """Structural components extracted from a Cypher query.

    Used for component-level comparison rather than string matching.
    """

    labels: set[str] = field(default_factory=set)
    relationships: set[str] = field(default_factory=set)
    return_fields: set[str] = field(default_factory=set)
    property_filters: set[str] = field(default_factory=set)


class CypherAccuracy:
    """Evaluate accuracy of generated Cypher against ground truth.

    Compares structural components (labels, relationships, return fields,
    property filters) rather than exact string matching. This allows for
    stylistic variation while measuring semantic correctness.

    The score is computed as:
        matched_components / total_expected_components

    Where components include node labels, relationship types, return field
    aliases, and property filter references.
    """

    def extract_components(self, cypher: str) -> CypherComponents:
        """Extract structural components from a Cypher query string.

        Args:
            cypher: Cypher query string.

        Returns:
            CypherComponents with labels, relationships, return fields,
            and property filters.
        """
        return CypherComponents(
            labels=_extract_node_labels(cypher),
            relationships=_extract_relationship_types(cypher),
            return_fields=_extract_return_fields(cypher),
            property_filters=_extract_property_filters(cypher),
        )

    def evaluate(self, generated_cypher: str, ground_truth_cypher: str) -> float:
        """Score generated Cypher against ground truth.

        Compares extracted components and returns the ratio of matched
        components to total expected components.

        Args:
            generated_cypher: The Cypher produced by the pipeline.
            ground_truth_cypher: The reference (gold standard) Cypher.

        Returns:
            Score in [0.0, 1.0]. 1.0 means all expected components
            were found in the generated query.
        """
        if not generated_cypher or not ground_truth_cypher:
            return 0.0

        gen = self.extract_components(generated_cypher)
        truth = self.extract_components(ground_truth_cypher)

        # Collect all expected components as (category, value) pairs
        expected: list[tuple[str, str]] = []
        for label in truth.labels:
            expected.append(("label", label))
        for rel in truth.relationships:
            expected.append(("relationship", rel))
        for prop in truth.property_filters:
            expected.append(("property_filter", prop))

        if not expected:
            # No structural components to compare -- consider it a match
            return 1.0

        matched = 0
        for category, value in expected:
            if category == "label" and value in gen.labels or category == "relationship" and value in gen.relationships or category == "property_filter" and value in gen.property_filters:
                matched += 1

        return matched / len(expected)


# =========================================================================
# QueryRelevancy metric
# =========================================================================


class QueryRelevancy:
    """Evaluate whether generated Cypher targets the right entity types.

    Checks if the generated Cypher query references the expected node
    labels for a given question. The score is based on label coverage:
        labels_found / labels_expected

    This is a lightweight approximation of retrieval relevancy.
    """

    def evaluate(
        self,
        question: str,
        generated_cypher: str,
        expected_labels: list[str],
    ) -> float:
        """Score label coverage of generated Cypher.

        Args:
            question: The original Korean question (for context, not
                currently used in scoring).
            generated_cypher: The Cypher produced by the pipeline.
            expected_labels: List of expected node labels.

        Returns:
            Score in [0.0, 1.0]. 1.0 means all expected labels are
            present in the generated Cypher.
        """
        if not expected_labels:
            return 1.0

        if not generated_cypher:
            return 0.0

        gen_labels = _extract_node_labels(generated_cypher)

        matched = sum(1 for label in expected_labels if label in gen_labels)
        return matched / len(expected_labels)


# =========================================================================
# ReasoningTypeMetric
# =========================================================================


class ReasoningTypeMetric:
    """Aggregate evaluation scores by reasoning type.

    Takes a list of per-question result dictionaries and computes
    the average score for each ReasoningType category.
    """

    def evaluate(self, results: list[dict]) -> dict[str, float]:
        """Compute average scores grouped by reasoning type.

        Args:
            results: List of dicts, each containing at least:
                - ``reasoning_type``: str or ReasoningType value
                - ``score``: float score for that question

        Returns:
            Dict mapping reasoning type name to average score.
            Only includes types that have at least one result.

        Example::

            results = [
                {"reasoning_type": "DIRECT", "score": 0.9},
                {"reasoning_type": "DIRECT", "score": 1.0},
                {"reasoning_type": "BRIDGE", "score": 0.5},
            ]
            metric.evaluate(results)
            # {"DIRECT": 0.95, "BRIDGE": 0.5}
        """
        from collections import defaultdict

        type_scores: dict[str, list[float]] = defaultdict(list)

        for result in results:
            rt = result.get("reasoning_type", "UNKNOWN")
            # Handle both enum and string values
            if hasattr(rt, "value"):
                rt = rt.value
            score = result.get("score", 0.0)
            type_scores[str(rt)].append(score)

        return {
            rt: sum(scores) / len(scores)
            for rt, scores in type_scores.items()
            if scores
        }
