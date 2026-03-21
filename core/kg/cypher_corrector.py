"""Rule-based Cypher query correction for the Text-to-Cypher pipeline.

Applies deterministic (no LLM) corrections to fix common issues found
during validation.  This is Stage 4 (Correct) of the 4-stage pipeline:
Parse -> Generate -> Validate -> **Correct**.

Usage::

    from kg.cypher_corrector import CypherCorrector

    corrector = CypherCorrector(
        valid_labels={"Vessel", "Port", "Berth"},
        valid_rel_types={"DOCKED_AT", "ON_VOYAGE"},
    )
    result = corrector.correct("MATCH (v:vessel) RETURN v")
    assert result.corrected == "MATCH (v:Vessel) RETURN v"
"""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass, field


@dataclass
class CorrectionResult:
    """Result of Cypher correction attempt.

    Attributes:
        original: The original Cypher query before correction.
        corrected: The corrected Cypher query (same as original if
            no corrections were needed).
        corrections_applied: Human-readable descriptions of each
            correction that was applied.
        was_modified: Whether any corrections were actually made.
    """

    original: str
    corrected: str
    corrections_applied: list[str] = field(default_factory=list)
    was_modified: bool = False


# Regex patterns
_LABEL_IN_NODE = re.compile(r"(\(\s*\w*\s*:)\s*([A-Za-z_]\w*)\s*(\))")
_REL_IN_BRACKET = re.compile(r"(\[\s*\w*\s*:)\s*([A-Za-z_]\w*)\s*(\])")
_RETURN_PATTERN = re.compile(r"\bRETURN\b", re.IGNORECASE)
_MATCH_PATTERN = re.compile(r"\bMATCH\b", re.IGNORECASE)


class CypherCorrector:
    """Applies rule-based corrections to Cypher queries.

    Corrections (no LLM needed):

    1. Fix common label case issues (``vessel`` -> ``Vessel``)
    2. Fix relationship type case (``docked_at`` -> ``DOCKED_AT``)
    3. Add missing RETURN clause
    4. Fix string comparison (``=`` -> ``CONTAINS`` for partial matches)

    Args:
        valid_labels: Set of canonical node labels for case correction.
        valid_rel_types: Set of canonical relationship types.
    """

    def __init__(
        self,
        valid_labels: set[str] | None = None,
        valid_rel_types: set[str] | None = None,
    ) -> None:
        self._valid_labels = valid_labels or set()
        self._valid_rel_types = valid_rel_types or set()

        # Build case-insensitive lookup maps
        self._label_lookup: dict[str, str] = {
            label.lower(): label for label in self._valid_labels
        }
        self._rel_lookup: dict[str, str] = {
            rel.upper(): rel for rel in self._valid_rel_types
        }

    @classmethod
    def from_maritime_ontology(cls) -> CypherCorrector:
        """Create a corrector pre-loaded with the maritime ontology.

        .. deprecated::
            Use ``kg.maritime_factories.create_maritime_corrector()`` instead.
            This method will be removed in the next major version.

        Returns:
            CypherCorrector with all maritime labels and relationship types.
        """
        warnings.warn(
            "from_maritime_ontology() is deprecated. "
            "Use kg.maritime_factories.create_maritime_corrector() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        from maritime.ontology.maritime_loader import load_maritime_ontology

        ontology = load_maritime_ontology()
        labels = {ot.name for ot in ontology.get_all_object_types()}
        rel_types = {lt.name for lt in ontology.get_all_link_types()}
        return cls(valid_labels=labels, valid_rel_types=rel_types)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def correct(self, cypher: str) -> CorrectionResult:
        """Apply all correction rules to a Cypher query.

        Applies corrections in order: label case, relationship type case,
        missing RETURN clause.  Each rule is idempotent.

        Args:
            cypher: The Cypher query string to correct.

        Returns:
            CorrectionResult with the corrected query and descriptions
            of all corrections applied.
        """
        if not cypher or not cypher.strip():
            return CorrectionResult(
                original=cypher,
                corrected=cypher,
                was_modified=False,
            )

        original = cypher
        all_corrections: list[str] = []

        # 1. Fix label case
        cypher, label_corrections = self._fix_label_case(cypher)
        all_corrections.extend(label_corrections)

        # 2. Fix relationship type case
        cypher, rel_corrections = self._fix_rel_type_case(cypher)
        all_corrections.extend(rel_corrections)

        # 3. Add missing RETURN clause
        cypher, return_corrections = self._add_return_clause(cypher)
        all_corrections.extend(return_corrections)

        was_modified = cypher != original

        return CorrectionResult(
            original=original,
            corrected=cypher,
            corrections_applied=all_corrections,
            was_modified=was_modified,
        )

    # ------------------------------------------------------------------
    # Correction rules
    # ------------------------------------------------------------------

    def _fix_label_case(self, cypher: str) -> tuple[str, list[str]]:
        """Fix node label casing.

        Maps incorrectly-cased labels to their canonical form using
        case-insensitive matching.  For example, ``vessel`` -> ``Vessel``,
        ``port`` -> ``Port``.

        Args:
            cypher: Cypher query string.

        Returns:
            Tuple of (corrected query, list of correction descriptions).
        """
        corrections: list[str] = []

        def _replace_label(match: re.Match[str]) -> str:
            prefix = match.group(1)    # e.g. "(v:"
            label = match.group(2)     # e.g. "vessel"
            suffix = match.group(3)    # e.g. ")"

            canonical = self._label_lookup.get(label.lower())
            if canonical and canonical != label:
                corrections.append(
                    f"Fixed label case: '{label}' -> '{canonical}'"
                )
                return f"{prefix}{canonical}{suffix}"
            return match.group(0)

        cypher = _LABEL_IN_NODE.sub(_replace_label, cypher)
        return cypher, corrections

    def _fix_rel_type_case(self, cypher: str) -> tuple[str, list[str]]:
        """Fix relationship type casing.

        Converts incorrectly-cased relationship types to their canonical
        SCREAMING_SNAKE_CASE form.  For example, ``docked_at`` ->
        ``DOCKED_AT``.

        Args:
            cypher: Cypher query string.

        Returns:
            Tuple of (corrected query, list of correction descriptions).
        """
        corrections: list[str] = []

        def _replace_rel(match: re.Match[str]) -> str:
            prefix = match.group(1)    # e.g. "[r:"
            rel_type = match.group(2)  # e.g. "docked_at"
            suffix = match.group(3)    # e.g. "]"

            canonical = self._rel_lookup.get(rel_type.upper())
            if canonical and canonical != rel_type:
                corrections.append(
                    f"Fixed relationship type case: "
                    f"'{rel_type}' -> '{canonical}'"
                )
                return f"{prefix}{canonical}{suffix}"
            return match.group(0)

        cypher = _REL_IN_BRACKET.sub(_replace_rel, cypher)
        return cypher, corrections

    def _add_return_clause(self, cypher: str) -> tuple[str, list[str]]:
        """Add RETURN clause if missing.

        When a query has a MATCH but no RETURN, appends a generic
        ``RETURN`` clause using the first node alias found.

        Args:
            cypher: Cypher query string.

        Returns:
            Tuple of (corrected query, list of correction descriptions).
        """
        corrections: list[str] = []

        if _MATCH_PATTERN.search(cypher) and not _RETURN_PATTERN.search(cypher):
            # Extract the first alias from the MATCH pattern
            alias_match = re.search(r"\(\s*(\w+)\s*:", cypher)
            if alias_match:
                alias = alias_match.group(1)
                cypher = cypher.rstrip().rstrip(";")
                cypher += f"\nRETURN {alias}"
                corrections.append(
                    f"Added missing RETURN clause: 'RETURN {alias}'"
                )
            else:
                # No alias found; add generic RETURN *
                cypher = cypher.rstrip().rstrip(";")
                cypher += "\nRETURN *"
                corrections.append(
                    "Added missing RETURN clause: 'RETURN *'"
                )

        return cypher, corrections
