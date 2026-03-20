"""Comprehensive unit tests for the Korean NL-to-StructuredQuery parser.

All tests are marked with ``@pytest.mark.unit`` and require no external
services (no Neo4j, no LLM).
"""

from __future__ import annotations

import pytest

from kg.nlp.nl_parser import NLParser
from kg.query_generator import QueryIntentType
from kg.types import FilterOperator, ReasoningType


@pytest.fixture()
def parser() -> NLParser:
    """Provide a fresh NLParser instance for each test."""
    return NLParser()


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIntentDetection:
    """Test _detect_intent correctly identifies FIND, COUNT, AGGREGATE."""

    def test_find_intent_default(self, parser: NLParser) -> None:
        """Plain query without count/aggregate keywords -> FIND."""
        result = parser.parse("부산항 근처 선박")
        assert result.query.intent.intent == QueryIntentType.FIND

    def test_count_intent_with_myeot(self, parser: NLParser) -> None:
        """'몇' keyword triggers COUNT intent."""
        result = parser.parse("선박 몇 척 있어?")
        assert result.query.intent.intent == QueryIntentType.COUNT

    def test_count_intent_with_gaesu(self, parser: NLParser) -> None:
        """'개수' keyword triggers COUNT intent."""
        result = parser.parse("부산항 선박 개수")
        assert result.query.intent.intent == QueryIntentType.COUNT

    def test_aggregate_intent_average(self, parser: NLParser) -> None:
        """'평균' keyword triggers AGGREGATE intent."""
        result = parser.parse("선박 평균 톤수")
        assert result.query.intent.intent == QueryIntentType.AGGREGATE

    def test_aggregate_intent_max(self, parser: NLParser) -> None:
        """'최대' keyword triggers AGGREGATE intent."""
        result = parser.parse("최대 속도 선박")
        assert result.query.intent.intent == QueryIntentType.AGGREGATE


# ---------------------------------------------------------------------------
# Entity extraction
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEntityExtraction:
    """Test _extract_entities maps Korean terms to Neo4j labels."""

    def test_vessel_extraction(self, parser: NLParser) -> None:
        """'선박' maps to Vessel label."""
        result = parser.parse("선박 목록")
        assert "Vessel" in result.query.object_types

    def test_port_extraction(self, parser: NLParser) -> None:
        """Named entity '부산항' maps to Port label."""
        result = parser.parse("부산항 정보")
        assert "Port" in result.query.object_types

    def test_multiple_entities(self, parser: NLParser) -> None:
        """Multiple terms in same query extract multiple labels."""
        result = parser.parse("부산항 컨테이너선 정보")
        labels = result.query.object_types
        assert "Port" in labels
        assert "CargoShip" in labels

    def test_tanker_extraction(self, parser: NLParser) -> None:
        """'유조선' maps to Tanker label."""
        result = parser.parse("유조선 현황")
        assert "Tanker" in result.query.object_types

    def test_facility_extraction(self, parser: NLParser) -> None:
        """'시험시설' maps to TestFacility label."""
        result = parser.parse("시험시설 정보")
        assert "TestFacility" in result.query.object_types


# ---------------------------------------------------------------------------
# Filter extraction
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFilterExtraction:
    """Test _extract_filters produces correct ExtractedFilter objects."""

    def test_named_entity_filter_busan(self, parser: NLParser) -> None:
        """'부산항' creates a filter on Port.unlocode = KRPUS."""
        result = parser.parse("부산항 선박")
        filter_fields = {f.field: f for f in result.query.filters}
        assert "unlocode" in filter_fields
        assert filter_fields["unlocode"].value == "KRPUS"

    def test_property_value_filter_container(self, parser: NLParser) -> None:
        """'컨테이너선' creates a vesselType = ContainerShip filter."""
        result = parser.parse("컨테이너선 목록")
        filter_fields = {f.field: f for f in result.query.filters}
        assert "vesselType" in filter_fields
        assert filter_fields["vesselType"].value == "ContainerShip"

    def test_numeric_gte_filter(self, parser: NLParser) -> None:
        """'5000톤 이상' creates tonnage >= 5000 filter."""
        result = parser.parse("5000톤 이상 선박")
        tonnage_filters = [f for f in result.query.filters if f.field == "tonnage"]
        assert len(tonnage_filters) >= 1
        f = tonnage_filters[0]
        assert f.value == 5000
        assert f.operator == FilterOperator.GREATER_THAN_OR_EQUALS

    def test_numeric_lt_filter(self, parser: NLParser) -> None:
        """'3000톤 미만' creates tonnage < 3000 filter."""
        result = parser.parse("3000톤 미만 선박")
        tonnage_filters = [f for f in result.query.filters if f.field == "tonnage"]
        assert len(tonnage_filters) >= 1
        f = tonnage_filters[0]
        assert f.value == 3000
        assert f.operator == FilterOperator.LESS_THAN

    def test_named_entity_incheon(self, parser: NLParser) -> None:
        """'인천항' creates a filter on Port.unlocode = KRICN."""
        result = parser.parse("인천항 정보")
        filter_fields = {f.field: f for f in result.query.filters}
        assert "unlocode" in filter_fields
        assert filter_fields["unlocode"].value == "KRICN"

    def test_status_filter(self, parser: NLParser) -> None:
        """'항해중' creates a currentStatus = UNDERWAY filter."""
        result = parser.parse("항해중 선박")
        status_filters = [f for f in result.query.filters if f.field == "currentStatus"]
        assert len(status_filters) >= 1
        assert status_filters[0].value == "UNDERWAY"


# ---------------------------------------------------------------------------
# Relationship extraction
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRelationshipExtraction:
    """Test _extract_relationships maps Korean keywords to relationship types."""

    def test_owned_by_relationship(self, parser: NLParser) -> None:
        """'소유한' maps to OWNED_BY relationship."""
        result = parser.parse("HMM이 소유한 선박")
        rel_types = [r.type for r in result.query.relationships]
        assert "OWNED_BY" in rel_types

    def test_docked_at_relationship(self, parser: NLParser) -> None:
        """'정박한' maps to DOCKED_AT relationship."""
        result = parser.parse("부산항에 정박한 선박")
        rel_types = [r.type for r in result.query.relationships]
        assert "DOCKED_AT" in rel_types

    def test_located_at_relationship(self, parser: NLParser) -> None:
        """'위치한' maps to LOCATED_AT relationship."""
        result = parser.parse("부산항에 위치한 시설")
        rel_types = [r.type for r in result.query.relationships]
        assert "LOCATED_AT" in rel_types


# ---------------------------------------------------------------------------
# Aggregation extraction
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAggregationExtraction:
    """Test _extract_aggregations detects aggregation functions."""

    def test_avg_aggregation(self, parser: NLParser) -> None:
        """'평균' triggers AVG aggregation."""
        result = parser.parse("선박 평균 톤수")
        assert result.query.aggregations is not None
        funcs = [a.function for a in result.query.aggregations]
        assert "AVG" in funcs

    def test_max_aggregation(self, parser: NLParser) -> None:
        """'최대' triggers MAX aggregation."""
        result = parser.parse("최대 속도 선박")
        assert result.query.aggregations is not None
        funcs = [a.function for a in result.query.aggregations]
        assert "MAX" in funcs


# ---------------------------------------------------------------------------
# Pagination extraction
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPaginationExtraction:
    """Test _extract_pagination detects '상위 N개' patterns."""

    def test_top_n_pagination(self, parser: NLParser) -> None:
        """'상위 10개' sets pagination.limit = 10."""
        result = parser.parse("상위 10개 선박")
        assert result.query.pagination is not None
        assert result.query.pagination.limit == 10

    def test_n_only_pagination(self, parser: NLParser) -> None:
        """'5개만' sets pagination.limit = 5."""
        result = parser.parse("선박 5개만 보여줘")
        assert result.query.pagination is not None
        assert result.query.pagination.limit == 5


# ---------------------------------------------------------------------------
# Full parse flow
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFullParseFlow:
    """Test complete Korean sentences through the full parse pipeline."""

    def test_busan_vessels_query(self, parser: NLParser) -> None:
        """'부산항 근처 선박' produces Port entity with unlocode filter."""
        result = parser.parse("부산항 근처 선박")
        assert "Port" in result.query.object_types
        assert "Vessel" in result.query.object_types
        assert any(f.field == "unlocode" and f.value == "KRPUS" for f in result.query.filters)
        assert result.query.intent.intent == QueryIntentType.FIND

    def test_container_ship_count(self, parser: NLParser) -> None:
        """'컨테이너선 몇 척' -> COUNT intent with vesselType filter."""
        result = parser.parse("컨테이너선 몇 척 있어?")
        assert result.query.intent.intent == QueryIntentType.COUNT
        assert any(f.field == "vesselType" and f.value == "ContainerShip" for f in result.query.filters)

    def test_complex_multi_filter(self, parser: NLParser) -> None:
        """Complex sentence with entity, numeric filter, and pagination."""
        result = parser.parse("부산항 5000톤 이상 컨테이너선 상위 10개")
        assert "Port" in result.query.object_types
        assert any(f.field == "unlocode" for f in result.query.filters)
        assert any(f.field == "tonnage" and f.value == 5000 for f in result.query.filters)
        assert any(f.field == "vesselType" for f in result.query.filters)
        assert result.query.pagination is not None
        assert result.query.pagination.limit == 10

    def test_empty_input(self, parser: NLParser) -> None:
        """Empty input produces empty StructuredQuery with zero confidence."""
        result = parser.parse("")
        assert result.confidence == 0.0
        assert result.query.object_types == []


# ---------------------------------------------------------------------------
# ParseResult confidence
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestParseResultConfidence:
    """Test confidence scoring of ParseResult."""

    def test_high_confidence_known_terms(self, parser: NLParser) -> None:
        """Query with well-known terms produces confidence > 0.5."""
        result = parser.parse("부산항 컨테이너선")
        assert result.confidence > 0.5

    def test_low_confidence_unknown_terms(self, parser: NLParser) -> None:
        """Query with unknown junk produces lower confidence."""
        result = parser.parse("알수없는단어들의나열")
        # Should still be low since nothing was resolved
        assert result.confidence <= 0.5


# ---------------------------------------------------------------------------
# Reasoning type classification
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestReasoningTypeClassification:
    """Test multi-hop reasoning type classification."""

    def test_direct_simple_query(self, parser: NLParser) -> None:
        """Simple entity lookup -> DIRECT."""
        result = parser.parse("부산항 정보 알려줘")
        assert result.query.reasoning_type == ReasoningType.DIRECT

    def test_bridge_possessive_chain(self, parser: NLParser) -> None:
        """Possessive chain '~의 ~' -> BRIDGE."""
        result = parser.parse("부산항에 정박중인 선박의 소유 기관")
        assert result.query.reasoning_type == ReasoningType.BRIDGE

    def test_bridge_multi_relationship(self, parser: NLParser) -> None:
        """Multiple relationship keywords -> BRIDGE."""
        result = parser.parse("KRISO가 운영하는 시설에서 수행한 실험")
        assert result.query.reasoning_type == ReasoningType.BRIDGE

    def test_comparison_keywords(self, parser: NLParser) -> None:
        """Comparison keywords -> COMPARISON."""
        result = parser.parse("내부연구원과 외부연구자의 데이터 접근 등급 비교")
        assert result.query.reasoning_type == ReasoningType.COMPARISON

    def test_intersection_keywords(self, parser: NLParser) -> None:
        """Intersection keywords -> INTERSECTION."""
        result = parser.parse("부산항과 인천항에 공통으로 입항한 선박")
        assert result.query.reasoning_type == ReasoningType.INTERSECTION

    def test_composition_ranking(self, parser: NLParser) -> None:
        """Ranking/aggregation -> COMPOSITION."""
        result = parser.parse("가장 많은 실험을 수행한 시험시설 Top 3")
        assert result.query.reasoning_type == ReasoningType.COMPOSITION

    def test_composition_total(self, parser: NLParser) -> None:
        """Aggregation with total -> COMPOSITION."""
        result = parser.parse("시험시설별 총 실험 횟수")
        assert result.query.reasoning_type == ReasoningType.COMPOSITION

    def test_comparison_vs(self, parser: NLParser) -> None:
        """'vs' keyword -> COMPARISON."""
        result = parser.parse("예인수조 vs 빙해수조 실험 비교")
        assert result.query.reasoning_type == ReasoningType.COMPARISON

    def test_intersection_both(self, parser: NLParser) -> None:
        """'둘 다' keyword -> INTERSECTION."""
        result = parser.parse("저항시험과 내항성능시험 둘 다 사용한 모형선")
        assert result.query.reasoning_type == ReasoningType.INTERSECTION

    def test_direct_default_fallback(self, parser: NLParser) -> None:
        """No special keywords -> defaults to DIRECT."""
        result = parser.parse("선박 목록")
        assert result.query.reasoning_type == ReasoningType.DIRECT

    def test_comparison_difference(self, parser: NLParser) -> None:
        """'차이' keyword -> COMPARISON."""
        result = parser.parse("부산항과 인천항의 입항 선박 수 차이")
        assert result.query.reasoning_type == ReasoningType.COMPARISON

    def test_intersection_simultaneous(self, parser: NLParser) -> None:
        """'동시에' keyword -> INTERSECTION."""
        result = parser.parse("부산항과 인천항에 동시에 접안한 선박")
        assert result.query.reasoning_type == ReasoningType.INTERSECTION

    def test_composition_average(self, parser: NLParser) -> None:
        """'평균' keyword -> COMPOSITION."""
        result = parser.parse("각 항구별 평균 입항 대기 시간")
        assert result.query.reasoning_type == ReasoningType.COMPOSITION

    def test_empty_input_defaults_direct(self, parser: NLParser) -> None:
        """Empty input produces DIRECT as default reasoning type."""
        result = parser.parse("")
        assert result.query.reasoning_type == ReasoningType.DIRECT
