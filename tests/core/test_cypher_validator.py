"""Unit tests for the CypherValidator.

All tests are marked with ``@pytest.mark.unit`` and require no external
services (no Neo4j, no LLM).
"""

from __future__ import annotations

import pytest

from kg.cypher_validator import CypherValidator, FailureType, ValidationResult

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
def validator() -> CypherValidator:
    """Provide a validator with known maritime labels and rels."""
    return CypherValidator.from_labels_and_types(VALID_LABELS, VALID_REL_TYPES)


@pytest.fixture()
def syntax_only_validator() -> CypherValidator:
    """Provide a validator with no ontology (syntax-only checks)."""
    return CypherValidator()


# ---------------------------------------------------------------------------
# ValidationResult dataclass
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestValidationResult:
    """Test the ValidationResult dataclass."""

    def test_default_values(self) -> None:
        """Default ValidationResult is valid with score 1.0."""
        result = ValidationResult(is_valid=True)
        assert result.is_valid is True
        assert result.errors == []
        assert result.warnings == []
        assert result.score == 1.0

    def test_custom_values(self) -> None:
        """ValidationResult accepts custom errors/warnings/score."""
        result = ValidationResult(
            is_valid=False,
            errors=["Missing RETURN"],
            warnings=["Wrong case"],
            score=0.5,
        )
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert len(result.warnings) == 1
        assert result.score == 0.5


# ---------------------------------------------------------------------------
# Syntax validation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSyntaxValidation:
    """Test basic Cypher syntax checks."""

    def test_valid_match_return(self, validator: CypherValidator) -> None:
        """Standard MATCH/RETURN query is valid."""
        result = validator.validate("MATCH (v:Vessel) RETURN v")
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_missing_match(self, validator: CypherValidator) -> None:
        """Query without MATCH clause has error."""
        result = validator.validate("RETURN 1")
        assert result.is_valid is False
        assert any("MATCH" in e for e in result.errors)

    def test_missing_return(self, validator: CypherValidator) -> None:
        """Query without RETURN clause has error."""
        result = validator.validate("MATCH (v:Vessel)")
        assert result.is_valid is False
        assert any("RETURN" in e for e in result.errors)

    def test_empty_string(self, validator: CypherValidator) -> None:
        """Empty string produces invalid result."""
        result = validator.validate("")
        assert result.is_valid is False
        assert result.score == 0.0

    def test_whitespace_only(self, validator: CypherValidator) -> None:
        """Whitespace-only string produces invalid result."""
        result = validator.validate("   ")
        assert result.is_valid is False

    def test_case_insensitive_keywords(
        self, validator: CypherValidator
    ) -> None:
        """MATCH and RETURN are recognized case-insensitively."""
        result = validator.validate("match (v:Vessel) return v")
        assert result.is_valid is True


# ---------------------------------------------------------------------------
# Label validation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLabelValidation:
    """Test node label checking against ontology."""

    def test_valid_label_vessel(self, validator: CypherValidator) -> None:
        """Known label 'Vessel' passes."""
        result = validator.validate("MATCH (v:Vessel) RETURN v")
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_valid_label_port(self, validator: CypherValidator) -> None:
        """Known label 'Port' passes."""
        result = validator.validate("MATCH (p:Port) RETURN p")
        assert result.is_valid is True

    def test_valid_label_test_facility(
        self, validator: CypherValidator
    ) -> None:
        """Known label 'TestFacility' passes."""
        result = validator.validate("MATCH (t:TestFacility) RETURN t")
        assert result.is_valid is True

    def test_invalid_label_ship(self, validator: CypherValidator) -> None:
        """Unknown label 'Ship' produces error."""
        result = validator.validate("MATCH (s:Ship) RETURN s")
        assert not result.is_valid
        assert any("Ship" in e for e in result.errors)

    def test_invalid_label_harbor(self, validator: CypherValidator) -> None:
        """Unknown label 'Harbor' produces error."""
        result = validator.validate("MATCH (h:Harbor) RETURN h")
        assert not result.is_valid
        assert any("Harbor" in e for e in result.errors)

    def test_invalid_label_unknown(self, validator: CypherValidator) -> None:
        """Completely unknown label produces error."""
        result = validator.validate("MATCH (x:FooBarBaz) RETURN x")
        assert not result.is_valid
        assert any("FooBarBaz" in e for e in result.errors)

    def test_wrong_case_label_warning(
        self, validator: CypherValidator
    ) -> None:
        """Wrong-case label (e.g., 'vessel') produces warning, not error."""
        result = validator.validate("MATCH (v:vessel) RETURN v")
        # 'vessel' maps case-insensitively to 'Vessel', so warning
        assert any("vessel" in w for w in result.warnings)

    def test_multiple_labels(self, validator: CypherValidator) -> None:
        """Query with multiple valid labels passes."""
        cypher = (
            "MATCH (v:Vessel)-[:DOCKED_AT]->(b:Berth) "
            "RETURN v, b"
        )
        result = validator.validate(cypher)
        assert result.is_valid is True

    def test_generic_node_label_skipped(
        self, validator: CypherValidator
    ) -> None:
        """Generic 'Node' label is skipped during validation."""
        result = validator.validate(
            "MATCH (n:Vessel)-[:ON_VOYAGE]->(t:Node) RETURN n"
        )
        assert result.is_valid is True


# ---------------------------------------------------------------------------
# Relationship type validation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRelationshipValidation:
    """Test relationship type checking against ontology."""

    def test_valid_rel_docked_at(self, validator: CypherValidator) -> None:
        """Known relationship 'DOCKED_AT' passes."""
        cypher = "MATCH (v:Vessel)-[r:DOCKED_AT]->(b:Berth) RETURN v, b"
        result = validator.validate(cypher)
        assert result.is_valid is True

    def test_valid_rel_on_voyage(self, validator: CypherValidator) -> None:
        """Known relationship 'ON_VOYAGE' passes."""
        cypher = "MATCH (v:Vessel)-[r:ON_VOYAGE]->(voy:Voyage) RETURN v"
        result = validator.validate(cypher)
        assert result.is_valid is True

    def test_invalid_rel_lives_in(self, validator: CypherValidator) -> None:
        """Unknown relationship 'LIVES_IN' produces error."""
        cypher = "MATCH (v:Vessel)-[r:LIVES_IN]->(p:Port) RETURN v"
        result = validator.validate(cypher)
        assert not result.is_valid
        assert any("LIVES_IN" in e for e in result.errors)

    def test_invalid_rel_friend_of(self, validator: CypherValidator) -> None:
        """Unknown relationship 'FRIEND_OF' produces error."""
        cypher = "MATCH (a:Vessel)-[r:FRIEND_OF]->(b:Vessel) RETURN a"
        result = validator.validate(cypher)
        assert not result.is_valid
        assert any("FRIEND_OF" in e for e in result.errors)

    def test_wrong_case_rel_warning(
        self, validator: CypherValidator
    ) -> None:
        """Wrong-case relationship type produces warning."""
        cypher = "MATCH (v:Vessel)-[r:docked_at]->(b:Berth) RETURN v"
        result = validator.validate(cypher)
        assert any("docked_at" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestValidationScoring:
    """Test the quality scoring mechanism."""

    def test_perfect_score(self, validator: CypherValidator) -> None:
        """Valid query with no issues gets score 1.0."""
        result = validator.validate("MATCH (v:Vessel) RETURN v")
        assert result.score == 1.0

    def test_score_decreases_with_errors(
        self, validator: CypherValidator
    ) -> None:
        """Errors decrease the score."""
        result = validator.validate("MATCH (s:Ship)")  # 2 errors
        assert result.score < 1.0

    def test_score_zero_for_empty(self, validator: CypherValidator) -> None:
        """Empty query gets score 0.0."""
        result = validator.validate("")
        assert result.score == 0.0

    def test_warnings_reduce_score_less(
        self, validator: CypherValidator
    ) -> None:
        """Warnings reduce score less than errors."""
        # This has a case warning only
        result = validator.validate("MATCH (v:vessel) RETURN v")
        assert result.score > 0.5


# ---------------------------------------------------------------------------
# Full validate() pipeline
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFullValidation:
    """Test the complete validate() method."""

    def test_complex_valid_query(self, validator: CypherValidator) -> None:
        """Complex valid query passes all checks."""
        cypher = (
            "MATCH (v:Vessel)-[r:CARRIES]->(c:Cargo)\n"
            "WHERE v.vesselType = $type\n"
            "RETURN v.name, c"
        )
        result = validator.validate(cypher)
        assert result.is_valid is True
        assert result.score == 1.0

    def test_multiple_errors(self, validator: CypherValidator) -> None:
        """Query with multiple problems accumulates errors."""
        cypher = "MATCH (s:Ship)-[:FRIEND_OF]->(h:Harbor)"
        result = validator.validate(cypher)
        assert result.is_valid is False
        # Should have errors for Ship, Harbor, FRIEND_OF, and missing RETURN
        assert len(result.errors) >= 3

    def test_syntax_only_mode(
        self, syntax_only_validator: CypherValidator
    ) -> None:
        """Without ontology, only syntax checks run."""
        result = syntax_only_validator.validate(
            "MATCH (v:AnythingGoes) RETURN v"
        )
        assert result.is_valid is True

    def test_from_labels_and_types_factory(self) -> None:
        """from_labels_and_types creates a working validator."""
        v = CypherValidator.from_labels_and_types(
            labels={"Alpha"}, rel_types={"LINKS_TO"}
        )
        result = v.validate("MATCH (a:Alpha)-[:LINKS_TO]->(b:Alpha) RETURN a")
        assert result.is_valid is True

    def test_count_query_valid(self, validator: CypherValidator) -> None:
        """COUNT query with RETURN is valid."""
        cypher = "MATCH (v:Vessel) RETURN count(v) AS total"
        result = validator.validate(cypher)
        assert result.is_valid is True


# ---------------------------------------------------------------------------
# Failure type classification (GraphRAG Part 11)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFailureTypeClassification:
    """Test FailureType classification per GraphRAG Part 11."""

    def test_schema_failure_missing_match(
        self, validator: CypherValidator
    ) -> None:
        """Missing MATCH clause is classified as SCHEMA failure."""
        result = validator.validate("RETURN 1")
        assert result.failure_type == FailureType.SCHEMA

    def test_schema_failure_missing_return(
        self, validator: CypherValidator
    ) -> None:
        """Missing RETURN clause is classified as SCHEMA failure."""
        result = validator.validate("MATCH (v:Vessel)")
        assert result.failure_type == FailureType.SCHEMA

    def test_schema_failure_invalid_label(
        self, validator: CypherValidator
    ) -> None:
        """Unknown node label is classified as SCHEMA failure."""
        result = validator.validate("MATCH (s:Ship) RETURN s")
        assert result.failure_type == FailureType.SCHEMA

    def test_schema_failure_invalid_rel_type(
        self, validator: CypherValidator
    ) -> None:
        """Unknown relationship type is classified as SCHEMA failure."""
        result = validator.validate(
            "MATCH (v:Vessel)-[:FRIEND_OF]->(p:Port) RETURN v"
        )
        assert result.failure_type == FailureType.SCHEMA

    def test_schema_failure_empty_query(
        self, validator: CypherValidator
    ) -> None:
        """Empty query is classified as SCHEMA failure."""
        result = validator.validate("")
        assert result.failure_type == FailureType.SCHEMA

    def test_schema_failure_multiple_errors(
        self, validator: CypherValidator
    ) -> None:
        """Query with both invalid label and missing RETURN is SCHEMA."""
        result = validator.validate("MATCH (s:Ship)-[:LIVES_IN]->(h:Harbor)")
        assert result.failure_type == FailureType.SCHEMA
        assert len(result.errors) >= 3

    def test_none_for_valid_query(
        self, validator: CypherValidator
    ) -> None:
        """Valid query is classified as NONE (no failure)."""
        result = validator.validate("MATCH (v:Vessel) RETURN v")
        assert result.failure_type == FailureType.NONE

    def test_none_for_complex_valid_query(
        self, validator: CypherValidator
    ) -> None:
        """Complex valid query with relationships is classified as NONE."""
        cypher = (
            "MATCH (v:Vessel)-[:DOCKED_AT]->(b:Berth) "
            "RETURN v.name, b"
        )
        result = validator.validate(cypher)
        assert result.failure_type == FailureType.NONE

    def test_failure_type_field_in_result(self) -> None:
        """ValidationResult includes failure_type with correct default."""
        result = ValidationResult(is_valid=True)
        assert result.failure_type == FailureType.NONE

    def test_failure_type_custom_value(self) -> None:
        """ValidationResult accepts custom failure_type."""
        result = ValidationResult(
            is_valid=False,
            errors=["test"],
            failure_type=FailureType.GENERATION,
        )
        assert result.failure_type == FailureType.GENERATION

    def test_classify_failure_type_static_method(self) -> None:
        """classify_failure_type works as a static method."""
        assert (
            CypherValidator.classify_failure_type(
                errors=["Missing MATCH clause"], warnings=[]
            )
            == FailureType.SCHEMA
        )
        assert (
            CypherValidator.classify_failure_type(errors=[], warnings=[])
            == FailureType.NONE
        )

    def test_retrieval_failure_missing_property(self) -> None:
        """Warnings about missing properties classify as RETRIEVAL."""
        assert (
            CypherValidator.classify_failure_type(
                errors=[],
                warnings=["Property 'fooBar' may not exist on queried labels"],
            )
            == FailureType.RETRIEVAL
        )

    def test_case_warning_not_retrieval(
        self, validator: CypherValidator
    ) -> None:
        """Wrong-case warning (without property issue) stays NONE."""
        result = validator.validate("MATCH (v:vessel) RETURN v")
        # Has a case warning but no property warning
        assert result.failure_type == FailureType.NONE

    def test_failure_type_enum_values(self) -> None:
        """FailureType enum has the expected string values."""
        assert FailureType.NONE.value == "none"
        assert FailureType.SCHEMA.value == "schema"
        assert FailureType.RETRIEVAL.value == "retrieval"
        assert FailureType.GENERATION.value == "generation"

    def test_failure_type_is_str_enum(self) -> None:
        """FailureType is a string enum for JSON serialization."""
        assert isinstance(FailureType.SCHEMA, str)
        assert FailureType.SCHEMA == "schema"
