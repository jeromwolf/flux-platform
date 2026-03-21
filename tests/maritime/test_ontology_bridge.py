"""Tests for the ontology-query bridge module.

Validates OntologyAwareCypherBuilder, validate_structured_query,
and get_ontology_context_for_query with the real maritime ontology.
"""

from __future__ import annotations

import warnings

import pytest

from maritime.ontology.maritime_loader import load_maritime_ontology
from kg.ontology_bridge import (
    OntologyAwareCypherBuilder,
    get_ontology_context_for_query,
    validate_structured_query,
)
from kg.query_generator import (
    ExtractedFilter,
    QueryIntent,
    RelationshipSpec,
    StructuredQuery,
)


@pytest.fixture(scope="module")
def maritime_ontology():
    """한 번만 로드하는 해사 온톨로지 픽스처."""
    return load_maritime_ontology()


# =========================================================================
# OntologyAwareCypherBuilder - 온톨로지 없이 (일반 CypherBuilder처럼 동작)
# =========================================================================


@pytest.mark.unit
class TestOntologyAwareCypherBuilderNoOntology:
    """온톨로지 없이 OntologyAwareCypherBuilder가 일반 CypherBuilder처럼 동작하는지 검증."""

    def test_no_ontology_acts_like_cypher_builder(self):
        """온톨로지 미설정 시 일반 CypherBuilder와 동일하게 동작."""
        query, params = (
            OntologyAwareCypherBuilder()
            .match("(v:Vessel)")
            .where("v.vesselType = $type", {"type": "ContainerShip"})
            .return_("v.name AS name")
            .limit(10)
            .build()
        )

        assert "MATCH (v:Vessel)" in query
        assert "v.vesselType = $type" in query
        assert "RETURN v.name AS name" in query
        assert "LIMIT 10" in query
        assert params == {"type": "ContainerShip"}

    def test_no_ontology_no_warnings(self):
        """온톨로지 미설정 시 존재하지 않는 레이블도 경고 없이 통과."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            OntologyAwareCypherBuilder().match("(x:FakeLabel)").build()
            assert len(w) == 0


# =========================================================================
# OntologyAwareCypherBuilder - 온톨로지 설정 시 검증
# =========================================================================


@pytest.mark.unit
class TestOntologyAwareCypherBuilderWithOntology:
    """온톨로지 설정 시 레이블/속성 검증 동작 확인."""

    def test_valid_label_no_warning(self, maritime_ontology):
        """유효한 레이블 사용 시 경고 없음."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            query, _ = (
                OntologyAwareCypherBuilder(ontology=maritime_ontology)
                .match("(v:Vessel)")
                .return_("v")
                .build()
            )
            ontology_warnings = [x for x in w if issubclass(x.category, UserWarning)]
            assert len(ontology_warnings) == 0
            assert "MATCH (v:Vessel)" in query

    def test_invalid_label_emits_warning(self, maritime_ontology):
        """존재하지 않는 레이블 사용 시 UserWarning 발생."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            query, _ = (
                OntologyAwareCypherBuilder(ontology=maritime_ontology)
                .match("(x:NonExistentLabel)")
                .return_("x")
                .build()
            )
            ontology_warnings = [x for x in w if issubclass(x.category, UserWarning)]
            assert len(ontology_warnings) == 1
            assert "NonExistentLabel" in str(ontology_warnings[0].message)
            # 경고만 발생하고 쿼리는 정상 빌드
            assert "MATCH (x:NonExistentLabel)" in query

    def test_invalid_property_emits_warning(self, maritime_ontology):
        """존재하지 않는 속성 사용 시 UserWarning 발생."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            query, params = (
                OntologyAwareCypherBuilder(ontology=maritime_ontology)
                .match("(v:Vessel)")
                .where("v.nonExistentProp = $val", {"val": "test"})
                .return_("v")
                .build()
            )
            ontology_warnings = [x for x in w if issubclass(x.category, UserWarning)]
            assert len(ontology_warnings) == 1
            assert "nonExistentProp" in str(ontology_warnings[0].message)
            # 경고만 발생하고 쿼리는 정상 빌드
            assert "v.nonExistentProp = $val" in query

    def test_valid_property_no_warning(self, maritime_ontology):
        """유효한 속성 사용 시 경고 없음."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            OntologyAwareCypherBuilder(ontology=maritime_ontology).match("(v:Vessel)").where(
                "v.vesselType = $type", {"type": "Tanker"}
            ).return_("v").build()
            ontology_warnings = [x for x in w if issubclass(x.category, UserWarning)]
            assert len(ontology_warnings) == 0

    def test_integration_full_query_no_warnings(self, maritime_ontology):
        """유효한 레이블+속성으로 완전한 쿼리 빌드 시 경고 없음."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            query, params = (
                OntologyAwareCypherBuilder(ontology=maritime_ontology)
                .match("(v:Vessel)")
                .where("v.vesselType = $type", {"type": "ContainerShip"})
                .where("v.flag = $flag", {"flag": "KR"})
                .return_("v.name AS name, v.mmsi AS mmsi")
                .order_by("name", "asc", "v")
                .limit(20)
                .build()
            )
            ontology_warnings = [x for x in w if issubclass(x.category, UserWarning)]
            assert len(ontology_warnings) == 0
            assert "MATCH (v:Vessel)" in query
            assert params["type"] == "ContainerShip"
            assert params["flag"] == "KR"


# =========================================================================
# validate_structured_query
# =========================================================================


@pytest.mark.unit
class TestValidateStructuredQuery:
    """validate_structured_query 함수의 검증 기능 테스트."""

    def test_valid_query_empty_warnings(self, maritime_ontology):
        """유효한 StructuredQuery는 빈 경고 목록을 반환."""
        sq = StructuredQuery(
            intent=QueryIntent(intent="FIND", confidence=0.9),
            object_types=["Vessel"],
            properties=["name", "mmsi", "vesselType"],
            filters=[ExtractedFilter(field="vesselType", operator="equals", value="ContainerShip")],
        )
        result = validate_structured_query(sq, maritime_ontology)
        assert result == []

    def test_invalid_label_returns_warning(self, maritime_ontology):
        """존재하지 않는 엔티티 레이블에 대해 경고 반환."""
        sq = StructuredQuery(
            intent=QueryIntent(intent="FIND"),
            object_types=["UnknownEntity"],
        )
        result = validate_structured_query(sq, maritime_ontology)
        assert len(result) == 1
        assert "UnknownEntity" in result[0]

    def test_invalid_property_returns_warning(self, maritime_ontology):
        """존재하지 않는 속성에 대해 경고 반환."""
        sq = StructuredQuery(
            intent=QueryIntent(intent="FIND"),
            object_types=["Vessel"],
            properties=["name", "nonExistentField"],
        )
        result = validate_structured_query(sq, maritime_ontology)
        assert len(result) == 1
        assert "nonExistentField" in result[0]

    def test_invalid_filter_property_returns_warning(self, maritime_ontology):
        """필터에서 존재하지 않는 속성에 대해 경고 반환."""
        sq = StructuredQuery(
            intent=QueryIntent(intent="FIND"),
            object_types=["Port"],
            filters=[ExtractedFilter(field="fakeProperty", operator="equals", value="test")],
        )
        result = validate_structured_query(sq, maritime_ontology)
        assert len(result) == 1
        assert "fakeProperty" in result[0]

    def test_invalid_relationship_returns_warning(self, maritime_ontology):
        """존재하지 않는 관계 타입에 대해 경고 반환."""
        sq = StructuredQuery(
            intent=QueryIntent(intent="FIND"),
            object_types=["Vessel"],
            relationships=[RelationshipSpec(type="FAKE_RELATIONSHIP", target_entity="Port")],
        )
        result = validate_structured_query(sq, maritime_ontology)
        assert len(result) == 1
        assert "FAKE_RELATIONSHIP" in result[0]

    def test_valid_relationship_no_warning(self, maritime_ontology):
        """유효한 관계 타입은 경고 없음."""
        sq = StructuredQuery(
            intent=QueryIntent(intent="FIND"),
            object_types=["Vessel"],
            relationships=[RelationshipSpec(type="DOCKED_AT", target_entity="Berth")],
        )
        result = validate_structured_query(sq, maritime_ontology)
        assert result == []


# =========================================================================
# get_ontology_context_for_query
# =========================================================================


@pytest.mark.unit
class TestGetOntologyContextForQuery:
    """get_ontology_context_for_query 함수의 출력 구조 테스트."""

    def test_returns_correct_structure(self, maritime_ontology):
        """반환 딕셔너리가 올바른 키를 포함."""
        ctx = get_ontology_context_for_query(maritime_ontology)
        assert "labels" in ctx
        assert "relationships" in ctx
        assert "properties" in ctx
        assert isinstance(ctx["labels"], list)
        assert isinstance(ctx["relationships"], list)
        assert isinstance(ctx["properties"], dict)

    def test_includes_vessel_and_port_labels(self, maritime_ontology):
        """Vessel과 Port 레이블이 포함되어야 함."""
        ctx = get_ontology_context_for_query(maritime_ontology)
        assert "Vessel" in ctx["labels"]
        assert "Port" in ctx["labels"]

    def test_includes_relationships(self, maritime_ontology):
        """주요 관계 타입이 포함되어야 함."""
        ctx = get_ontology_context_for_query(maritime_ontology)
        assert "DOCKED_AT" in ctx["relationships"]
        assert "ON_VOYAGE" in ctx["relationships"]

    def test_properties_contain_vessel_fields(self, maritime_ontology):
        """Vessel 엔티티의 속성 목록이 포함되어야 함."""
        ctx = get_ontology_context_for_query(maritime_ontology)
        assert "Vessel" in ctx["properties"]
        vessel_props = ctx["properties"]["Vessel"]
        assert "mmsi" in vessel_props
        assert "vesselType" in vessel_props
        assert "name" in vessel_props

    def test_labels_are_sorted(self, maritime_ontology):
        """레이블 목록이 정렬되어 있어야 함."""
        ctx = get_ontology_context_for_query(maritime_ontology)
        assert ctx["labels"] == sorted(ctx["labels"])

    def test_relationships_are_sorted(self, maritime_ontology):
        """관계 타입 목록이 정렬되어 있어야 함."""
        ctx = get_ontology_context_for_query(maritime_ontology)
        assert ctx["relationships"] == sorted(ctx["relationships"])
