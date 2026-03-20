"""Unit tests for the CypherCorrector.

All tests are marked with ``@pytest.mark.unit`` and require no external
services (no Neo4j, no LLM).
"""

from __future__ import annotations

import pytest

from kg.cypher_corrector import CorrectionResult, CypherCorrector

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_LABELS = {
    "Vessel",
    "Port",
    "Berth",
    "Organization",
    "TestFacility",
    "Voyage",
    "Cargo",
    "SeaArea",
    "Experiment",
    "Incident",
}

VALID_REL_TYPES = {
    "DOCKED_AT",
    "OWNED_BY",
    "OPERATES",
    "ON_VOYAGE",
    "CARRIES",
    "LOCATED_AT",
    "CONDUCTED_AT",
    "INVOLVES",
}


@pytest.fixture()
def corrector() -> CypherCorrector:
    """Provide a corrector with known maritime labels and rels."""
    return CypherCorrector(
        valid_labels=VALID_LABELS,
        valid_rel_types=VALID_REL_TYPES,
    )


@pytest.fixture()
def empty_corrector() -> CypherCorrector:
    """Provide a corrector with no valid labels/rels."""
    return CypherCorrector()


# ---------------------------------------------------------------------------
# CorrectionResult dataclass
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCorrectionResult:
    """Test the CorrectionResult dataclass."""

    def test_default_values(self) -> None:
        """Default CorrectionResult has empty corrections."""
        result = CorrectionResult(
            original="MATCH (v:Vessel) RETURN v",
            corrected="MATCH (v:Vessel) RETURN v",
        )
        assert result.corrections_applied == []
        assert result.was_modified is False

    def test_custom_values(self) -> None:
        """CorrectionResult accepts custom fields."""
        result = CorrectionResult(
            original="MATCH (v:vessel) RETURN v",
            corrected="MATCH (v:Vessel) RETURN v",
            corrections_applied=["Fixed label case: 'vessel' -> 'Vessel'"],
            was_modified=True,
        )
        assert result.was_modified is True
        assert len(result.corrections_applied) == 1


# ---------------------------------------------------------------------------
# Label case correction
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLabelCaseCorrection:
    """Test label case fixing."""

    def test_lowercase_vessel(self, corrector: CypherCorrector) -> None:
        """'vessel' -> 'Vessel'."""
        result = corrector.correct("MATCH (v:vessel) RETURN v")
        assert "Vessel" in result.corrected
        assert result.was_modified is True
        assert any("vessel" in c and "Vessel" in c for c in result.corrections_applied)

    def test_lowercase_port(self, corrector: CypherCorrector) -> None:
        """'port' -> 'Port'."""
        result = corrector.correct("MATCH (p:port) RETURN p")
        assert "Port" in result.corrected
        assert result.was_modified is True

    def test_uppercase_vessel(self, corrector: CypherCorrector) -> None:
        """'VESSEL' -> 'Vessel' (all-caps to PascalCase)."""
        result = corrector.correct("MATCH (v:VESSEL) RETURN v")
        assert "Vessel" in result.corrected
        assert result.was_modified is True

    def test_mixed_case_berth(self, corrector: CypherCorrector) -> None:
        """'berth' -> 'Berth'."""
        result = corrector.correct("MATCH (b:berth) RETURN b")
        assert "Berth" in result.corrected
        assert result.was_modified is True

    def test_correct_label_unchanged(
        self, corrector: CypherCorrector
    ) -> None:
        """Already-correct 'Vessel' stays unchanged."""
        result = corrector.correct("MATCH (v:Vessel) RETURN v")
        assert result.corrected == "MATCH (v:Vessel) RETURN v"
        assert result.was_modified is False

    def test_multiple_labels_corrected(
        self, corrector: CypherCorrector
    ) -> None:
        """Multiple wrong-case labels are all corrected."""
        cypher = "MATCH (v:vessel)-[:DOCKED_AT]->(b:berth) RETURN v, b"
        result = corrector.correct(cypher)
        assert "Vessel" in result.corrected
        assert "Berth" in result.corrected
        assert result.was_modified is True
        assert len(result.corrections_applied) == 2

    def test_unknown_label_left_alone(
        self, corrector: CypherCorrector
    ) -> None:
        """Labels not in valid set are left unchanged."""
        result = corrector.correct("MATCH (s:Ship) RETURN s")
        assert "Ship" in result.corrected
        assert result.was_modified is False


# ---------------------------------------------------------------------------
# Relationship type case correction
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRelTypeCaseCorrection:
    """Test relationship type case fixing."""

    def test_lowercase_docked_at(self, corrector: CypherCorrector) -> None:
        """'docked_at' -> 'DOCKED_AT'."""
        cypher = "MATCH (v:Vessel)-[r:docked_at]->(b:Berth) RETURN v"
        result = corrector.correct(cypher)
        assert "DOCKED_AT" in result.corrected
        assert result.was_modified is True
        assert any(
            "docked_at" in c and "DOCKED_AT" in c
            for c in result.corrections_applied
        )

    def test_mixedcase_on_voyage(self, corrector: CypherCorrector) -> None:
        """'on_Voyage' -> 'ON_VOYAGE' (mixed case)."""
        cypher = "MATCH (v:Vessel)-[r:on_Voyage]->(voy:Voyage) RETURN v"
        result = corrector.correct(cypher)
        assert "ON_VOYAGE" in result.corrected
        assert result.was_modified is True

    def test_correct_rel_unchanged(self, corrector: CypherCorrector) -> None:
        """Already-correct 'DOCKED_AT' stays unchanged."""
        cypher = "MATCH (v:Vessel)-[r:DOCKED_AT]->(b:Berth) RETURN v"
        result = corrector.correct(cypher)
        assert result.was_modified is False

    def test_unknown_rel_left_alone(
        self, corrector: CypherCorrector
    ) -> None:
        """Unknown relationship types are left unchanged."""
        cypher = "MATCH (v:Vessel)-[r:FRIEND_OF]->(b:Vessel) RETURN v"
        result = corrector.correct(cypher)
        assert "FRIEND_OF" in result.corrected
        assert result.was_modified is False


# ---------------------------------------------------------------------------
# Missing RETURN clause
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAddReturnClause:
    """Test adding missing RETURN clause."""

    def test_add_return_with_alias(self, corrector: CypherCorrector) -> None:
        """Missing RETURN adds 'RETURN v' using first alias."""
        result = corrector.correct("MATCH (v:Vessel)")
        assert "RETURN v" in result.corrected
        assert result.was_modified is True
        assert any("RETURN" in c for c in result.corrections_applied)

    def test_return_already_present(
        self, corrector: CypherCorrector
    ) -> None:
        """RETURN already present does not add another."""
        cypher = "MATCH (v:Vessel) RETURN v"
        result = corrector.correct(cypher)
        assert result.corrected.count("RETURN") == 1

    def test_add_return_complex_query(
        self, corrector: CypherCorrector
    ) -> None:
        """Missing RETURN on complex query uses first alias."""
        cypher = "MATCH (v:Vessel)-[r:CARRIES]->(c:Cargo)\nWHERE v.name = $name"
        result = corrector.correct(cypher)
        assert "RETURN v" in result.corrected
        assert result.was_modified is True


# ---------------------------------------------------------------------------
# No corrections needed
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNoCorrections:
    """Test that valid queries are not modified."""

    def test_perfect_query_unchanged(
        self, corrector: CypherCorrector
    ) -> None:
        """A perfectly valid query is returned unchanged."""
        cypher = "MATCH (v:Vessel)-[r:DOCKED_AT]->(b:Berth) RETURN v, b"
        result = corrector.correct(cypher)
        assert result.corrected == cypher
        assert result.was_modified is False
        assert len(result.corrections_applied) == 0

    def test_empty_string(self, corrector: CypherCorrector) -> None:
        """Empty string returns empty result."""
        result = corrector.correct("")
        assert result.corrected == ""
        assert result.was_modified is False

    def test_empty_corrector_no_changes(
        self, empty_corrector: CypherCorrector
    ) -> None:
        """Corrector with no valid labels/rels makes no label/rel corrections."""
        result = empty_corrector.correct(
            "MATCH (v:vessel) RETURN v"
        )
        # Without valid labels, case correction does not apply
        assert result.was_modified is False


# ---------------------------------------------------------------------------
# Combined corrections
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCombinedCorrections:
    """Test that multiple corrections stack correctly."""

    def test_label_and_rel_fix(self, corrector: CypherCorrector) -> None:
        """Both label case and rel type case are fixed together."""
        cypher = "MATCH (v:vessel)-[r:docked_at]->(b:berth) RETURN v"
        result = corrector.correct(cypher)
        assert "Vessel" in result.corrected
        assert "DOCKED_AT" in result.corrected
        assert "Berth" in result.corrected
        assert result.was_modified is True
        assert len(result.corrections_applied) >= 3

    def test_label_fix_and_add_return(
        self, corrector: CypherCorrector
    ) -> None:
        """Label fix + missing RETURN are both applied."""
        cypher = "MATCH (v:vessel)"
        result = corrector.correct(cypher)
        assert "Vessel" in result.corrected
        assert "RETURN" in result.corrected
        assert result.was_modified is True
        assert len(result.corrections_applied) >= 2
