"""Extended unit tests for domains/maritime/factories.py.

Covers create_maritime_validator, create_maritime_corrector, and
create_maritime_detector with various mock configurations to push
coverage beyond 80%.

All tests are @pytest.mark.unit and require no external services.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _Named:
    """Minimal stand-in for ObjectTypeDefinition / LinkTypeDefinition."""

    def __init__(self, name: str) -> None:
        self.name = name
        # CypherValidator._extract_ontology_schema checks obj_type.properties
        # and calls .keys() on it; None is falsy so the branch is skipped.
        self.properties: dict | None = None


def _make_ontology_mock(
    labels: set[str] | None = None,
    rel_types: set[str] | None = None,
) -> MagicMock:
    """Build a minimal mock Ontology that factories will consume.

    Uses explicit sentinel ``None`` to distinguish "use defaults" from
    "caller deliberately passed an empty set".
    """
    if labels is None:
        labels = {"Vessel", "Port", "Berth", "Voyage"}
    if rel_types is None:
        rel_types = {"DOCKED_AT", "ON_VOYAGE", "OWNS"}

    mock_ont = MagicMock()

    # get_all_object_types() returns a list of objects with .name
    mock_ont.get_all_object_types.return_value = [
        _Named(label) for label in labels
    ]
    # get_all_link_types() returns a list of objects with .name
    mock_ont.get_all_link_types.return_value = [
        _Named(rt) for rt in rel_types
    ]
    return mock_ont


# ---------------------------------------------------------------------------
# create_maritime_validator
# ---------------------------------------------------------------------------


_LOADER_PATH = "maritime.ontology.maritime_loader.load_maritime_ontology"


class TestCreateMaritimeValidator:
    """Tests for create_maritime_validator()."""

    @pytest.mark.unit
    def test_returns_cypher_validator_instance(self) -> None:
        """create_maritime_validator() returns a CypherValidator."""
        from kg.cypher_validator import CypherValidator

        mock_ont = _make_ontology_mock()
        with patch(_LOADER_PATH, return_value=mock_ont):
            from maritime.factories import create_maritime_validator

            validator = create_maritime_validator()
        assert isinstance(validator, CypherValidator)

    @pytest.mark.unit
    def test_validator_has_ontology_labels(self) -> None:
        """Validator is loaded with maritime ontology labels."""
        mock_ont = _make_ontology_mock(labels={"Vessel", "Port", "Tanker"})
        with patch(_LOADER_PATH, return_value=mock_ont):
            from maritime.factories import create_maritime_validator

            validator = create_maritime_validator()

        # Validate a simple Vessel query -- should pass
        result = validator.validate("MATCH (v:Vessel) RETURN v")
        assert result is not None

    @pytest.mark.unit
    def test_validator_load_ontology_called_once(self) -> None:
        """load_maritime_ontology() is called exactly once per factory call."""
        mock_ont = _make_ontology_mock()
        with patch(_LOADER_PATH, return_value=mock_ont) as mock_load:
            from maritime.factories import create_maritime_validator

            create_maritime_validator()

        mock_load.assert_called_once()

    @pytest.mark.unit
    def test_validator_uses_returned_ontology(self) -> None:
        """Validator is constructed with the ontology returned by loader."""
        mock_ont = _make_ontology_mock()
        with patch(_LOADER_PATH, return_value=mock_ont):
            from maritime.factories import create_maritime_validator

            validator = create_maritime_validator()

        # The internal ontology reference should be the mock
        assert validator._ontology is mock_ont

    @pytest.mark.unit
    def test_validator_with_empty_ontology(self) -> None:
        """Validator works even when ontology has no labels or rel types."""
        mock_ont = _make_ontology_mock(labels=set(), rel_types=set())
        with patch(_LOADER_PATH, return_value=mock_ont):
            from maritime.factories import create_maritime_validator

            validator = create_maritime_validator()

        from kg.cypher_validator import CypherValidator

        assert isinstance(validator, CypherValidator)

    @pytest.mark.unit
    def test_multiple_calls_return_independent_instances(self) -> None:
        """Each call to create_maritime_validator() creates a new instance."""
        mock_ont = _make_ontology_mock()
        with patch(_LOADER_PATH, return_value=mock_ont):
            from maritime.factories import create_maritime_validator

            v1 = create_maritime_validator()
            v2 = create_maritime_validator()

        assert v1 is not v2


# ---------------------------------------------------------------------------
# create_maritime_corrector
# ---------------------------------------------------------------------------


class TestCreateMaritimeCorrtor:
    """Tests for create_maritime_corrector()."""

    @pytest.mark.unit
    def test_returns_cypher_corrector_instance(self) -> None:
        """create_maritime_corrector() returns a CypherCorrector."""
        from kg.cypher_corrector import CypherCorrector

        mock_ont = _make_ontology_mock()
        with patch(_LOADER_PATH, return_value=mock_ont):
            from maritime.factories import create_maritime_corrector

            corrector = create_maritime_corrector()

        assert isinstance(corrector, CypherCorrector)

    @pytest.mark.unit
    def test_corrector_has_valid_labels(self) -> None:
        """Corrector receives labels extracted from ontology object types."""
        mock_ont = _make_ontology_mock(labels={"Vessel", "Port", "Cargo"})
        with patch(_LOADER_PATH, return_value=mock_ont):
            from maritime.factories import create_maritime_corrector

            corrector = create_maritime_corrector()

        # _valid_labels on corrector should include all ontology labels
        assert "Vessel" in corrector._valid_labels
        assert "Port" in corrector._valid_labels
        assert "Cargo" in corrector._valid_labels

    @pytest.mark.unit
    def test_corrector_has_valid_rel_types(self) -> None:
        """Corrector receives rel types extracted from ontology link types."""
        mock_ont = _make_ontology_mock(rel_types={"DOCKED_AT", "ON_VOYAGE"})
        with patch(_LOADER_PATH, return_value=mock_ont):
            from maritime.factories import create_maritime_corrector

            corrector = create_maritime_corrector()

        assert "DOCKED_AT" in corrector._valid_rel_types
        assert "ON_VOYAGE" in corrector._valid_rel_types

    @pytest.mark.unit
    def test_corrector_load_ontology_called_once(self) -> None:
        """load_maritime_ontology() is called exactly once."""
        mock_ont = _make_ontology_mock()
        with patch(_LOADER_PATH, return_value=mock_ont) as mock_load:
            from maritime.factories import create_maritime_corrector

            create_maritime_corrector()

        mock_load.assert_called_once()

    @pytest.mark.unit
    def test_corrector_can_correct_label_case(self) -> None:
        """Corrector created by factory can fix label casing."""
        mock_ont = _make_ontology_mock(labels={"Vessel"}, rel_types=set())
        with patch(_LOADER_PATH, return_value=mock_ont):
            from maritime.factories import create_maritime_corrector

            corrector = create_maritime_corrector()

        result = corrector.correct("MATCH (v:vessel) RETURN v")
        # The corrector should fix lowercase 'vessel' -> 'Vessel'
        assert "Vessel" in result.corrected

    @pytest.mark.unit
    def test_corrector_with_empty_ontology(self) -> None:
        """Corrector works even when ontology is empty."""
        mock_ont = _make_ontology_mock(labels=set(), rel_types=set())
        with patch(_LOADER_PATH, return_value=mock_ont):
            from maritime.factories import create_maritime_corrector

            corrector = create_maritime_corrector()

        from kg.cypher_corrector import CypherCorrector

        assert isinstance(corrector, CypherCorrector)
        assert corrector._valid_labels == set()
        assert corrector._valid_rel_types == set()

    @pytest.mark.unit
    def test_multiple_calls_return_independent_instances(self) -> None:
        """Each call returns a new CypherCorrector instance."""
        mock_ont = _make_ontology_mock()
        with patch(_LOADER_PATH, return_value=mock_ont):
            from maritime.factories import create_maritime_corrector

            c1 = create_maritime_corrector()
            c2 = create_maritime_corrector()

        assert c1 is not c2


# ---------------------------------------------------------------------------
# create_maritime_detector
# ---------------------------------------------------------------------------


_SYNONYMS_PATH = "maritime.nlp.maritime_terms.ENTITY_SYNONYMS"
_NAMED_PATH = "maritime.nlp.maritime_terms.NAMED_ENTITIES"


class TestCreateMaritimeDetector:
    """Tests for create_maritime_detector()."""

    _DUMMY_SYNONYMS: dict[str, str] = {
        "선박": "Vessel",
        "항구": "Port",
        "화물선": "CargoShip",
    }
    _DUMMY_NAMED_ENTITIES: dict = {
        "부산항": {"label": "Port", "key": "unlocode", "value": "KRPUS"},
        "HMM": {"label": "Organization", "key": "orgId", "value": "ORG-HMM"},
    }

    @pytest.mark.unit
    def test_returns_hallucination_detector_instance(self) -> None:
        """create_maritime_detector() returns a HallucinationDetector."""
        from kg.hallucination_detector import HallucinationDetector

        mock_ont = _make_ontology_mock()
        with (
            patch(_LOADER_PATH, return_value=mock_ont),
            patch(_SYNONYMS_PATH, self._DUMMY_SYNONYMS),
            patch(_NAMED_PATH, self._DUMMY_NAMED_ENTITIES),
        ):
            from maritime.factories import create_maritime_detector

            detector = create_maritime_detector()

        assert isinstance(detector, HallucinationDetector)

    @pytest.mark.unit
    def test_detector_known_labels_includes_ontology(self) -> None:
        """Detector known_labels includes labels from ontology object types."""
        mock_ont = _make_ontology_mock(labels={"Vessel", "Port", "Tanker"})
        with (
            patch(_LOADER_PATH, return_value=mock_ont),
            patch(_SYNONYMS_PATH, {}),
            patch(_NAMED_PATH, {}),
        ):
            from maritime.factories import create_maritime_detector

            detector = create_maritime_detector()

        assert "Vessel" in detector._known_labels
        assert "Port" in detector._known_labels

    @pytest.mark.unit
    def test_detector_known_labels_includes_synonym_values(self) -> None:
        """Detector known_labels includes values from ENTITY_SYNONYMS."""
        mock_ont = _make_ontology_mock(labels=set(), rel_types=set())
        synonyms = {"화물선": "CargoShip", "탱커": "Tanker"}
        with (
            patch(_LOADER_PATH, return_value=mock_ont),
            patch(_SYNONYMS_PATH, synonyms),
            patch(_NAMED_PATH, {}),
        ):
            from maritime.factories import create_maritime_detector

            detector = create_maritime_detector()

        assert "CargoShip" in detector._known_labels
        assert "Tanker" in detector._known_labels

    @pytest.mark.unit
    def test_detector_known_names_includes_named_entity_keys(self) -> None:
        """Detector known_names includes keys from NAMED_ENTITIES."""
        mock_ont = _make_ontology_mock(labels=set(), rel_types=set())
        named = {"부산항": {"label": "Port"}, "인천항": {"label": "Port"}}
        with (
            patch(_LOADER_PATH, return_value=mock_ont),
            patch(_SYNONYMS_PATH, {}),
            patch(_NAMED_PATH, named),
        ):
            from maritime.factories import create_maritime_detector

            detector = create_maritime_detector()

        assert "부산항" in detector._known_names
        assert "인천항" in detector._known_names

    @pytest.mark.unit
    def test_detector_known_names_includes_hardcoded_names(self) -> None:
        """Detector known_names always includes the hardcoded KRISO names."""
        mock_ont = _make_ontology_mock(labels=set(), rel_types=set())
        with (
            patch(_LOADER_PATH, return_value=mock_ont),
            patch(_SYNONYMS_PATH, {}),
            patch(_NAMED_PATH, {}),
        ):
            from maritime.factories import create_maritime_detector

            detector = create_maritime_detector()

        # These are hardcoded in the factory body
        assert "KRISO" in detector._known_names
        assert "부산항" in detector._known_names
        assert "HMM" in detector._known_names

    @pytest.mark.unit
    def test_detector_synonym_map_passed_correctly(self) -> None:
        """synonym_map on detector equals the ENTITY_SYNONYMS dict."""
        mock_ont = _make_ontology_mock(labels=set(), rel_types=set())
        synonyms = {"선박": "Vessel", "항구": "Port"}
        with (
            patch(_LOADER_PATH, return_value=mock_ont),
            patch(_SYNONYMS_PATH, synonyms),
            patch(_NAMED_PATH, {}),
        ):
            from maritime.factories import create_maritime_detector

            detector = create_maritime_detector()

        assert detector._synonym_map == synonyms

    @pytest.mark.unit
    def test_detector_known_entities_passed_correctly(self) -> None:
        """known_entities on detector equals the NAMED_ENTITIES dict."""
        mock_ont = _make_ontology_mock(labels=set(), rel_types=set())
        named = {"HMM": {"label": "Organization"}}
        with (
            patch(_LOADER_PATH, return_value=mock_ont),
            patch(_SYNONYMS_PATH, {}),
            patch(_NAMED_PATH, named),
        ):
            from maritime.factories import create_maritime_detector

            detector = create_maritime_detector()

        assert detector._known_entities == named

    @pytest.mark.unit
    def test_detector_ontology_failure_is_silenced(self) -> None:
        """If load_maritime_ontology raises, detector still returns."""
        from kg.hallucination_detector import HallucinationDetector

        with (
            patch(_LOADER_PATH, side_effect=Exception("ontology unavailable")),
            patch(_SYNONYMS_PATH, {}),
            patch(_NAMED_PATH, {}),
        ):
            from maritime.factories import create_maritime_detector

            detector = create_maritime_detector()

        # The factory has a try/except so detector is still created
        assert isinstance(detector, HallucinationDetector)
        # The hardcoded known_names still present
        assert "KRISO" in detector._known_names

    @pytest.mark.unit
    def test_detector_known_labels_combined_ontology_and_synonyms(
        self,
    ) -> None:
        """known_labels combines ontology labels AND synonym values."""
        mock_ont = _make_ontology_mock(labels={"Vessel"}, rel_types=set())
        synonyms = {"화물선": "CargoShip"}
        with (
            patch(_LOADER_PATH, return_value=mock_ont),
            patch(_SYNONYMS_PATH, synonyms),
            patch(_NAMED_PATH, {}),
        ):
            from maritime.factories import create_maritime_detector

            detector = create_maritime_detector()

        assert "Vessel" in detector._known_labels
        assert "CargoShip" in detector._known_labels

    @pytest.mark.unit
    def test_multiple_calls_return_independent_instances(self) -> None:
        """Each call to create_maritime_detector() returns a new instance."""
        mock_ont = _make_ontology_mock()
        with (
            patch(_LOADER_PATH, return_value=mock_ont),
            patch(_SYNONYMS_PATH, {}),
            patch(_NAMED_PATH, {}),
        ):
            from maritime.factories import create_maritime_detector

            d1 = create_maritime_detector()
            d2 = create_maritime_detector()

        assert d1 is not d2
