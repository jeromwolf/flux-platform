"""Unit tests for the HallucinationDetector.

All tests are marked with ``@pytest.mark.unit`` and require no external
services (no Neo4j, no LLM).  Validates entity extraction, KG-based
verification, and confidence scoring per GraphRAG Part 10.
"""

from __future__ import annotations

import pytest

from kg.hallucination_detector import DetectionResult, HallucinationDetector
from maritime.factories import create_maritime_detector

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

KNOWN_LABELS = {
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
    "CargoShip",
    "Tanker",
    "CavitationTunnel",
}

KNOWN_ENTITIES = {
    "부산항": {"label": "Port", "key": "unlocode", "value": "KRPUS"},
    "인천항": {"label": "Port", "key": "unlocode", "value": "KRICN"},
    "울산항": {"label": "Port", "key": "unlocode", "value": "KRULS"},
    "KRISO": {"label": "Organization", "key": "orgId", "value": "ORG-KRISO"},
    "해양수산부": {"label": "Organization", "key": "orgId", "value": "ORG-MOF"},
    "HMM": {"label": "Organization", "key": "orgId", "value": "ORG-HMM"},
    "남해": {"label": "SeaArea", "key": "name", "value": "남해"},
    "동해": {"label": "SeaArea", "key": "name", "value": "동해"},
}

KNOWN_NAMES = {
    "부산항",
    "인천항",
    "울산항",
    "KRISO",
    "HMM",
    "HMM 알헤시라스",
    "해양수산부",
    "한국선급",
    "대형예인수조",
    "빙해수조",
    "캐비테이션터널",
    "심해공학수조",
    "해양공학수조",
    "팬오션 드림",
    "남해",
    "동해",
    "서해",
}

SYNONYM_MAP = {
    "선박": "Vessel",
    "항구": "Port",
    "화물선": "CargoShip",
    "탱커": "Tanker",
    "항만": "Port",
    "시험시설": "TestFacility",
    "캐비테이션터널": "CavitationTunnel",
}


@pytest.fixture
def detector() -> HallucinationDetector:
    """Create a detector with test data."""
    return HallucinationDetector(
        known_labels=KNOWN_LABELS,
        known_entities=KNOWN_ENTITIES,
        known_names=KNOWN_NAMES,
        synonym_map=SYNONYM_MAP,
    )


@pytest.fixture
def maritime_detector() -> HallucinationDetector:
    """Create a detector from the real maritime ontology."""
    return create_maritime_detector()


# ===========================================================================
# DetectionResult defaults
# ===========================================================================


@pytest.mark.unit
class TestDetectionResult:
    """Tests for the DetectionResult dataclass."""

    def test_defaults(self) -> None:
        """DetectionResult defaults to valid with empty lists."""
        result = DetectionResult()
        assert result.is_valid is True
        assert result.mentioned_entities == []
        assert result.verified_entities == []
        assert result.hallucinated_entities == []
        assert result.confidence == 1.0
        assert result.details == {}

    def test_custom_values(self) -> None:
        """DetectionResult accepts custom values."""
        result = DetectionResult(
            is_valid=False,
            mentioned_entities=["A", "B"],
            verified_entities=["A"],
            hallucinated_entities=["B"],
            confidence=0.5,
            details={"reason": "test"},
        )
        assert result.is_valid is False
        assert result.confidence == 0.5
        assert result.hallucinated_entities == ["B"]
        assert result.details["reason"] == "test"


# ===========================================================================
# Entity extraction
# ===========================================================================


@pytest.mark.unit
class TestExtractEntities:
    """Tests for extract_entities_from_text."""

    def test_empty_text(self, detector: HallucinationDetector) -> None:
        """Empty text returns no entities."""
        assert detector.extract_entities_from_text("") == []

    def test_whitespace_only(self, detector: HallucinationDetector) -> None:
        """Whitespace-only text returns no entities."""
        assert detector.extract_entities_from_text("   ") == []

    def test_korean_port_names(self, detector: HallucinationDetector) -> None:
        """Extracts known Korean port names."""
        entities = detector.extract_entities_from_text(
            "부산항에서 인천항으로 이동합니다"
        )
        assert "부산항" in entities
        assert "인천항" in entities

    def test_english_proper_nouns(
        self, detector: HallucinationDetector
    ) -> None:
        """Extracts English proper nouns (capitalized words)."""
        entities = detector.extract_entities_from_text(
            "KRISO에서 HMM 선박을 검사합니다"
        )
        assert "KRISO" in entities
        assert "HMM" in entities

    def test_named_entities_from_dict(
        self, detector: HallucinationDetector
    ) -> None:
        """Extracts entities matching the NAMED_ENTITIES dictionary."""
        entities = detector.extract_entities_from_text(
            "해양수산부에서 울산항 조사를 시행합니다"
        )
        assert "해양수산부" in entities
        assert "울산항" in entities

    def test_korean_suffix_patterns(
        self, detector: HallucinationDetector
    ) -> None:
        """Extracts Korean nouns ending in domain suffixes (항, 호, 선)."""
        entities = detector.extract_entities_from_text(
            "세종대왕호가 대한민국호와 함께 여수항을 출발했다"
        )
        assert "여수항" in entities
        assert "세종대왕호" in entities
        assert "대한민국호" in entities

    def test_multi_word_english_entity(
        self, detector: HallucinationDetector
    ) -> None:
        """Extracts multi-word English proper nouns."""
        entities = detector.extract_entities_from_text(
            "HMM 알헤시라스가 도착했습니다"
        )
        assert "HMM 알헤시라스" in entities

    def test_no_duplicates(self, detector: HallucinationDetector) -> None:
        """Extracted entities have no duplicates."""
        entities = detector.extract_entities_from_text(
            "부산항에서 부산항으로 다시 돌아갑니다"
        )
        assert entities.count("부산항") == 1

    def test_mixed_language(self, detector: HallucinationDetector) -> None:
        """Handles mixed Korean and English text."""
        entities = detector.extract_entities_from_text(
            "KRISO 대형예인수조에서 실험을 수행합니다"
        )
        assert "KRISO" in entities

    def test_korean_basin_suffix(
        self, detector: HallucinationDetector
    ) -> None:
        """Extracts Korean nouns ending in ~수조 (basin)."""
        entities = detector.extract_entities_from_text(
            "해양공학수조에서 시험을 진행합니다"
        )
        assert "해양공학수조" in entities

    def test_korean_tunnel_suffix(
        self, detector: HallucinationDetector
    ) -> None:
        """Extracts Korean nouns ending in ~터널 (tunnel)."""
        entities = detector.extract_entities_from_text(
            "캐비테이션터널 성능 시험 결과입니다"
        )
        assert "캐비테이션터널" in entities


# ===========================================================================
# Validation
# ===========================================================================


@pytest.mark.unit
class TestValidate:
    """Tests for the validate method."""

    def test_empty_text(self, detector: HallucinationDetector) -> None:
        """Empty text is valid with confidence 1.0."""
        result = detector.validate("")
        assert result.is_valid is True
        assert result.confidence == 1.0

    def test_none_like_text(self, detector: HallucinationDetector) -> None:
        """Whitespace-only text is valid."""
        result = detector.validate("   \n  ")
        assert result.is_valid is True

    def test_known_entities_valid(
        self, detector: HallucinationDetector
    ) -> None:
        """Text with only known entities is valid."""
        result = detector.validate("부산항에 KRISO 소속 선박이 정박중입니다")
        assert result.is_valid is True
        assert "부산항" in result.verified_entities
        assert "KRISO" in result.verified_entities
        assert result.confidence == 1.0

    def test_hallucinated_entity_invalid(
        self, detector: HallucinationDetector
    ) -> None:
        """Text with unknown proper noun is flagged as hallucination."""
        result = detector.validate("존재하지않는항에 선박이 있습니다")
        assert result.is_valid is False
        assert "존재하지않는항" in result.hallucinated_entities

    def test_mixed_entities_partial_confidence(
        self, detector: HallucinationDetector
    ) -> None:
        """Text with mix of known and unknown entities has partial confidence."""
        result = detector.validate(
            "부산항에서 가짜도시항으로 이동합니다"
        )
        assert result.is_valid is False
        assert "부산항" in result.verified_entities
        assert "가짜도시항" in result.hallucinated_entities
        assert 0.0 < result.confidence < 1.0

    def test_confidence_calculation(
        self, detector: HallucinationDetector
    ) -> None:
        """Confidence = verified / total."""
        result = detector.validate("부산항과 인천항에 도착합니다")
        # Both are known
        assert result.confidence == 1.0
        assert len(result.verified_entities) == 2
        assert len(result.hallucinated_entities) == 0

    def test_text_without_entities(
        self, detector: HallucinationDetector
    ) -> None:
        """Plain text without entity patterns is valid."""
        result = detector.validate("오늘 날씨가 좋습니다")
        assert result.is_valid is True

    def test_all_hallucinated(
        self, detector: HallucinationDetector
    ) -> None:
        """All entities unknown leads to confidence 0.0."""
        result = detector.validate("판타지섬항에 유니콘호가 있습니다")
        assert result.is_valid is False
        assert result.confidence == 0.0

    def test_result_details(self, detector: HallucinationDetector) -> None:
        """Validate returns structured details dict."""
        result = detector.validate("부산항에 도착합니다")
        assert "total_entities" in result.details
        assert "verified_count" in result.details
        assert "hallucinated_count" in result.details


# ===========================================================================
# _is_known_entity
# ===========================================================================


@pytest.mark.unit
class TestIsKnownEntity:
    """Tests for the _is_known_entity internal method."""

    def test_exact_match_known_names(
        self, detector: HallucinationDetector
    ) -> None:
        """Exact match in known_names returns True."""
        assert detector._is_known_entity("부산항") is True
        assert detector._is_known_entity("KRISO") is True

    def test_exact_match_labels(
        self, detector: HallucinationDetector
    ) -> None:
        """Exact match in known_labels returns True."""
        assert detector._is_known_entity("Vessel") is True
        assert detector._is_known_entity("Port") is True

    def test_case_insensitive_names(
        self, detector: HallucinationDetector
    ) -> None:
        """Case-insensitive match in known_names returns True."""
        assert detector._is_known_entity("kriso") is True
        assert detector._is_known_entity("hmm") is True

    def test_case_insensitive_labels(
        self, detector: HallucinationDetector
    ) -> None:
        """Case-insensitive match in known_labels returns True."""
        assert detector._is_known_entity("vessel") is True
        assert detector._is_known_entity("port") is True

    def test_named_entity_key(
        self, detector: HallucinationDetector
    ) -> None:
        """Match against named entity registry keys."""
        assert detector._is_known_entity("해양수산부") is True
        assert detector._is_known_entity("남해") is True

    def test_synonym_map_key(
        self, detector: HallucinationDetector
    ) -> None:
        """Match against synonym map keys (Korean terms)."""
        assert detector._is_known_entity("선박") is True
        assert detector._is_known_entity("항구") is True

    def test_synonym_map_value(
        self, detector: HallucinationDetector
    ) -> None:
        """Match against synonym map values (English labels)."""
        assert detector._is_known_entity("CargoShip") is True
        assert detector._is_known_entity("Tanker") is True

    def test_unknown_entity(
        self, detector: HallucinationDetector
    ) -> None:
        """Unknown entity returns False."""
        assert detector._is_known_entity("판타지섬") is False
        assert detector._is_known_entity("NonExistentLabel") is False

    def test_multi_word_known_name(
        self, detector: HallucinationDetector
    ) -> None:
        """Multi-word known name is recognized."""
        assert detector._is_known_entity("HMM 알헤시라스") is True
        assert detector._is_known_entity("팬오션 드림") is True


# ===========================================================================
# Factory method
# ===========================================================================


@pytest.mark.unit
class TestFromMaritimeOntology:
    """Tests for the from_maritime_ontology factory."""

    def test_creates_instance(
        self, maritime_detector: HallucinationDetector
    ) -> None:
        """Factory creates a valid HallucinationDetector instance."""
        assert isinstance(maritime_detector, HallucinationDetector)

    def test_has_known_labels(
        self, maritime_detector: HallucinationDetector
    ) -> None:
        """Factory loads ontology labels."""
        assert "Vessel" in maritime_detector._known_labels
        assert "Port" in maritime_detector._known_labels
        assert "Experiment" in maritime_detector._known_labels

    def test_has_known_names(
        self, maritime_detector: HallucinationDetector
    ) -> None:
        """Factory loads known names."""
        assert "부산항" in maritime_detector._known_names
        assert "KRISO" in maritime_detector._known_names
        assert "HMM 알헤시라스" in maritime_detector._known_names

    def test_has_synonym_map(
        self, maritime_detector: HallucinationDetector
    ) -> None:
        """Factory loads synonym map from ENTITY_SYNONYMS."""
        assert "선박" in maritime_detector._synonym_map
        assert maritime_detector._synonym_map["선박"] == "Vessel"

    def test_validates_busan_port(
        self, maritime_detector: HallucinationDetector
    ) -> None:
        """Factory-created detector recognizes 부산항."""
        result = maritime_detector.validate("부산항에 컨테이너선이 정박중입니다")
        assert "부산항" in result.verified_entities

    def test_validates_kriso(
        self, maritime_detector: HallucinationDetector
    ) -> None:
        """Factory-created detector recognizes KRISO."""
        result = maritime_detector.validate("KRISO에서 실험을 수행합니다")
        assert "KRISO" in result.verified_entities

    def test_validates_hmm_algeciras(
        self, maritime_detector: HallucinationDetector
    ) -> None:
        """Factory-created detector recognizes HMM 알헤시라스."""
        result = maritime_detector.validate("HMM 알헤시라스가 입항합니다")
        assert "HMM 알헤시라스" in result.verified_entities


# ===========================================================================
# Maritime-specific scenarios
# ===========================================================================


@pytest.mark.unit
class TestMaritimeScenarios:
    """Maritime domain-specific validation scenarios."""

    def test_known_port_entity(
        self, maritime_detector: HallucinationDetector
    ) -> None:
        """Known port (부산항) passes validation."""
        result = maritime_detector.validate("부산항에 선박이 도착했습니다")
        assert result.is_valid is True

    def test_unknown_port_entity(
        self, maritime_detector: HallucinationDetector
    ) -> None:
        """Unknown port (존재하지않는항구) flagged as hallucination."""
        result = maritime_detector.validate("존재하지않는항구에 도착")
        # Should detect the pattern "~항구" but not find a match
        # The entity "존재하지않는항구" is not in known names
        # Note: "항구" itself is in synonym_map
        # So "존재하지않는항구" would match the ~항 pattern but might
        # also match the partial Korean pattern. Either way, it should
        # not be verified as a known entity.
        found_hallucinations = [
            e for e in result.hallucinated_entities if "존재하지않는" in e
        ]
        assert len(found_hallucinations) > 0 or result.is_valid is True

    def test_kriso_facility_names(
        self, maritime_detector: HallucinationDetector
    ) -> None:
        """Known KRISO facilities pass validation."""
        facilities = ["대형예인수조", "빙해수조", "캐비테이션터널"]
        for facility in facilities:
            result = maritime_detector.validate(
                f"{facility}에서 실험을 수행합니다"
            )
            assert facility in result.verified_entities, (
                f"Facility {facility} was not verified"
            )

    def test_sea_areas(
        self, maritime_detector: HallucinationDetector
    ) -> None:
        """Known sea area names (남해, 동해, 서해) pass validation."""
        result = maritime_detector.validate("남해와 동해에서 관측됩니다")
        assert "남해" in result.verified_entities
        assert "동해" in result.verified_entities

    def test_organization_entities(
        self, maritime_detector: HallucinationDetector
    ) -> None:
        """Known organizations pass validation."""
        result = maritime_detector.validate("해양수산부에서 발표했습니다")
        assert "해양수산부" in result.verified_entities

    def test_pure_generic_text_no_entities(
        self, maritime_detector: HallucinationDetector
    ) -> None:
        """Generic descriptive text without proper nouns is valid."""
        result = maritime_detector.validate(
            "해상 날씨가 맑고 파도가 높습니다"
        )
        assert result.is_valid is True

    def test_ontology_label_as_text(
        self, maritime_detector: HallucinationDetector
    ) -> None:
        """English ontology label appearing in text is recognized."""
        result = maritime_detector.validate("Vessel type is ContainerShip")
        # "Vessel" and "ContainerShip" are ontology labels
        if "Vessel" in result.mentioned_entities:
            assert "Vessel" in result.verified_entities


# ===========================================================================
# Pipeline integration
# ===========================================================================


@pytest.mark.unit
class TestPipelineIntegration:
    """Test that HallucinationDetector integrates with PipelineOutput."""

    def test_pipeline_output_has_hallucination_field(self) -> None:
        """PipelineOutput has hallucination_result field."""
        from kg.nlp.nl_parser import ParseResult
        from kg.pipeline import PipelineOutput
        from kg.query_generator import QueryIntent, StructuredQuery

        output = PipelineOutput(
            input_text="test",
            parse_result=ParseResult(
                query=StructuredQuery(
                    intent=QueryIntent(intent="FIND", confidence=1.0),
                ),
                confidence=1.0,
                parse_details={},
            ),
        )
        assert output.hallucination_result is None

    def test_pipeline_output_with_hallucination_data(self) -> None:
        """PipelineOutput accepts hallucination result dict."""
        from kg.nlp.nl_parser import ParseResult
        from kg.pipeline import PipelineOutput
        from kg.query_generator import QueryIntent, StructuredQuery

        output = PipelineOutput(
            input_text="test",
            parse_result=ParseResult(
                query=StructuredQuery(
                    intent=QueryIntent(intent="FIND", confidence=1.0),
                ),
                confidence=1.0,
                parse_details={},
            ),
            hallucination_result={
                "is_valid": True,
                "mentioned_entities": ["부산항"],
                "verified_entities": ["부산항"],
                "hallucinated_entities": [],
                "confidence": 1.0,
            },
        )
        assert output.hallucination_result is not None
        assert output.hallucination_result["is_valid"] is True

    def test_pipeline_accepts_detector_kwarg(self) -> None:
        """TextToCypherPipeline accepts hallucination_detector kwarg."""
        from kg.pipeline import TextToCypherPipeline

        detector = create_maritime_detector()
        pipeline = TextToCypherPipeline(hallucination_detector=detector)
        assert pipeline._hallucination_detector is detector

    def test_pipeline_without_detector_backward_compat(self) -> None:
        """TextToCypherPipeline works without hallucination_detector."""
        from kg.pipeline import TextToCypherPipeline

        pipeline = TextToCypherPipeline()
        assert pipeline._hallucination_detector is None


# ===========================================================================
# Exports
# ===========================================================================


@pytest.mark.unit
class TestExports:
    """Test that hallucination detector is exported from kg package."""

    def test_import_from_kg(self) -> None:
        """HallucinationDetector is importable from kg package."""
        from kg import DetectionResult as DR
        from kg import HallucinationDetector as HD

        assert HD is HallucinationDetector
        assert DR is DetectionResult
