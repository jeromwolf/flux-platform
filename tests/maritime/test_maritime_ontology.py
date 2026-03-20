"""Maritime Ontology 단위 테스트.

TC-B01 ~ TC-B07: kg/ontology/maritime_ontology.py의 ENTITY_LABELS,
RELATIONSHIP_TYPES, PROPERTY_DEFINITIONS 데이터 정합성 검증.
TC-C01 ~ TC-C06: kg/ontology/maritime_loader.py의 로딩/내보내기 검증.

모든 테스트는 Neo4j 없이 순수 Python으로 동작한다.
"""

from __future__ import annotations

import pytest

from kg.ontology.core import Ontology
from kg.ontology.maritime_loader import (
    export_ontology_to_cypher,
    get_schema_for_llm,
    load_maritime_ontology,
)
from kg.ontology.maritime_ontology import (
    ENTITY_LABELS,
    PROPERTY_DEFINITIONS,
    RELATIONSHIP_TYPES,
)

# =========================================================================
# TC-B01: ENTITY_LABELS 개수 확인
# =========================================================================


@pytest.mark.unit
class TestEntityLabels:
    """ENTITY_LABELS 데이터 정합성 검증."""

    def test_entity_labels_count(self) -> None:
        """TC-B01: ENTITY_LABELS에 126개 이상 항목이 존재해야 한다."""
        count = len(ENTITY_LABELS)
        assert count >= 126, f"ENTITY_LABELS에 126개 이상 필요하나 {count}개만 존재"

    def test_core_entities_exist(self) -> None:
        """TC-B02: 핵심 엔티티 레이블이 존재해야 한다."""
        core_entities = [
            "Vessel",
            "CargoShip",
            "Tanker",
            "FishingVessel",
            "Port",
            "TradePort",
            "Berth",
            "Anchorage",
            "Voyage",
            "PortCall",
            "Incident",
            "Collision",
            "WeatherCondition",
            "SeaArea",
            "EEZ",
            "Regulation",
            "COLREG",
            "SOLAS",
            "MARPOL",
            "Document",
            "Organization",
            "Person",
            "Experiment",
            "TestFacility",
            "ModelShip",
            "User",
            "Role",
            "DataClass",
            "Workflow",
            "AIModel",
            "AIAgent",
            "AISData",
            "SatelliteImage",
        ]
        for entity in core_entities:
            assert entity in ENTITY_LABELS, f"핵심 엔티티 '{entity}'가 ENTITY_LABELS에 없음"

    def test_entity_labels_are_strings(self) -> None:
        """TC-B02-b: 모든 엔티티 설명이 비어있지 않은 문자열이어야 한다."""
        for label, description in ENTITY_LABELS.items():
            assert isinstance(label, str), f"레이블 키가 문자열이 아님: {label}"
            assert isinstance(description, str), f"설명이 문자열이 아님: {label}"
            assert len(description) > 0, f"설명이 비어있음: {label}"

    def test_entity_labels_pascal_case(self) -> None:
        """TC-B02-c: 엔티티 레이블은 PascalCase여야 한다."""
        for label in ENTITY_LABELS:
            assert label[0].isupper(), f"엔티티 레이블 '{label}'이 대문자로 시작하지 않음"


# =========================================================================
# TC-B03 ~ B04: RELATIONSHIP_TYPES 검증
# =========================================================================


@pytest.mark.unit
class TestRelationshipTypes:
    """RELATIONSHIP_TYPES 데이터 정합성 검증."""

    def test_relationship_count(self) -> None:
        """TC-B03: RELATIONSHIP_TYPES에 83개 이상 항목이 존재해야 한다."""
        count = len(RELATIONSHIP_TYPES)
        assert count >= 83, f"RELATIONSHIP_TYPES에 83개 이상 필요하나 {count}개만 존재"

    def test_relationship_schema_structure(self) -> None:
        """TC-B04: 각 관계에 필수 키가 존재해야 한다."""
        required_keys = {"type", "from_label", "to_label", "description", "properties"}
        for i, rel in enumerate(RELATIONSHIP_TYPES):
            for key in required_keys:
                assert key in rel, (
                    f"RELATIONSHIP_TYPES[{i}]에 '{key}' 키가 없음: {rel.get('type', 'unknown')}"
                )

    def test_relationship_types_screaming_snake_case(self) -> None:
        """TC-B04-b: 관계 타입 이름은 SCREAMING_SNAKE_CASE여야 한다."""
        for rel in RELATIONSHIP_TYPES:
            rel_type = rel["type"]
            assert rel_type == rel_type.upper(), (
                f"관계 타입 '{rel_type}'이 SCREAMING_SNAKE_CASE가 아님"
            )
            assert " " not in rel_type, f"관계 타입 '{rel_type}'에 공백이 포함됨"

    def test_core_relationships_exist(self) -> None:
        """TC-B04-c: 핵심 관계 타입이 존재해야 한다."""
        core_rels = [
            "LOCATED_AT",
            "DOCKED_AT",
            "ON_VOYAGE",
            "FROM_PORT",
            "TO_PORT",
            "CARRIES",
            "PRODUCES",
            "AFFECTS",
            "INVOLVES",
            "APPLIES_TO",
            "CONDUCTED_AT",
            "TESTED",
            "HAS_ROLE",
            "CAN_ACCESS",
        ]
        rel_types = {rel["type"] for rel in RELATIONSHIP_TYPES}
        for rel_type in core_rels:
            assert rel_type in rel_types, f"핵심 관계 '{rel_type}'이 RELATIONSHIP_TYPES에 없음"


# =========================================================================
# TC-B05: 관계의 참조 무결성
# =========================================================================


@pytest.mark.unit
class TestRelationshipReferentialIntegrity:
    """관계 타입의 from_label/to_label 참조 무결성."""

    # 일부 관계는 추상 타입(Observation 등)을 참조하며 ENTITY_LABELS에 없을 수 있음
    KNOWN_ABSTRACT_TYPES = {"Observation", "Node", "Target"}

    def test_from_label_exists(self) -> None:
        """TC-B05-a: 모든 관계의 from_label이 ENTITY_LABELS에 존재하거나 알려진 추상 타입."""
        missing = []
        for rel in RELATIONSHIP_TYPES:
            from_label = rel["from_label"]
            if from_label not in ENTITY_LABELS and from_label not in self.KNOWN_ABSTRACT_TYPES:
                missing.append((rel["type"], "from_label", from_label))

        assert len(missing) == 0, f"참조 무결성 위반 (from_label): {missing}"

    def test_to_label_exists(self) -> None:
        """TC-B05-b: 모든 관계의 to_label이 ENTITY_LABELS에 존재하거나 알려진 추상 타입."""
        missing = []
        for rel in RELATIONSHIP_TYPES:
            to_label = rel["to_label"]
            if to_label not in ENTITY_LABELS and to_label not in self.KNOWN_ABSTRACT_TYPES:
                missing.append((rel["type"], "to_label", to_label))

        assert len(missing) == 0, f"참조 무결성 위반 (to_label): {missing}"


# =========================================================================
# TC-B06: PROPERTY_DEFINITIONS 구조 검증
# =========================================================================


@pytest.mark.unit
class TestPropertyDefinitions:
    """PROPERTY_DEFINITIONS 구조 검증."""

    VALID_TYPES = {
        "STRING",
        "INTEGER",
        "FLOAT",
        "BOOLEAN",
        "DATE",
        "DATETIME",
        "POINT",
        "LIST<STRING>",
        "LIST<FLOAT>",
        "LIST<INTEGER>",
    }

    def test_property_types_valid(self) -> None:
        """TC-B06: 모든 프로퍼티 타입이 올바른 타입 문자열이어야 한다."""
        invalid = []
        for entity_name, props in PROPERTY_DEFINITIONS.items():
            for prop_name, prop_type in props.items():
                if prop_type not in self.VALID_TYPES:
                    invalid.append((entity_name, prop_name, prop_type))

        assert len(invalid) == 0, f"유효하지 않은 프로퍼티 타입: {invalid}"

    # Observation은 하위 타입(AISObservation 등)의 공통 프로퍼티를 정의하는 추상 타입
    KNOWN_ABSTRACT_PROPERTY_TYPES = {"Observation"}

    def test_property_definitions_entities_exist(self) -> None:
        """TC-B07: PROPERTY_DEFINITIONS의 키가 ENTITY_LABELS에 존재해야 한다.

        Observation 등 하위 타입의 공통 프로퍼티를 정의하는 추상 타입은 예외.
        """
        missing = []
        for entity_name in PROPERTY_DEFINITIONS:
            if (
                entity_name not in ENTITY_LABELS
                and entity_name not in self.KNOWN_ABSTRACT_PROPERTY_TYPES
            ):
                missing.append(entity_name)

        assert len(missing) == 0, (
            f"PROPERTY_DEFINITIONS에 정의된 엔티티가 ENTITY_LABELS에 없음: {missing}"
        )

    def test_vessel_properties_complete(self) -> None:
        """TC-B06-b: Vessel 엔티티의 핵심 프로퍼티가 정의되어야 한다."""
        vessel_props = PROPERTY_DEFINITIONS.get("Vessel", {})
        expected_props = ["mmsi", "imo", "name", "vesselType", "flag"]
        for prop in expected_props:
            assert prop in vessel_props, f"Vessel에 '{prop}' 프로퍼티가 없음"

    def test_port_properties_complete(self) -> None:
        """TC-B06-c: Port 엔티티의 핵심 프로퍼티가 정의되어야 한다."""
        port_props = PROPERTY_DEFINITIONS.get("Port", {})
        expected_props = ["unlocode", "name", "country", "location"]
        for prop in expected_props:
            assert prop in port_props, f"Port에 '{prop}' 프로퍼티가 없음"

    def test_property_definitions_count(self) -> None:
        """TC-B06-d: PROPERTY_DEFINITIONS에 상당수 엔티티가 정의되어야 한다."""
        count = len(PROPERTY_DEFINITIONS)
        assert count >= 20, f"PROPERTY_DEFINITIONS에 20개 이상 엔티티 필요하나 {count}개만 존재"


# =========================================================================
# TC-C01 ~ C06: Maritime Loader 검증
# =========================================================================


@pytest.mark.unit
class TestMaritimeLoader:
    """load_maritime_ontology() 로더 검증."""

    def test_load_success(self) -> None:
        """TC-C01: load_maritime_ontology() 반환 타입이 Ontology 인스턴스."""
        ontology = load_maritime_ontology()
        assert isinstance(ontology, Ontology), "반환 타입이 Ontology가 아님"
        assert ontology.name == "maritime"

    def test_object_type_count(self) -> None:
        """TC-C02: 로딩된 ObjectType 수가 ENTITY_LABELS 수와 일치."""
        ontology = load_maritime_ontology()
        loaded_count = len(ontology.get_all_object_types())
        expected_count = len(ENTITY_LABELS)
        assert loaded_count == expected_count, (
            f"ObjectType 수 불일치: {loaded_count} != {expected_count}"
        )

    def test_link_type_loaded(self) -> None:
        """TC-C03: LinkType이 1개 이상 로딩되어야 한다."""
        ontology = load_maritime_ontology()
        link_count = len(ontology.get_all_link_types())
        assert link_count > 0, "LinkType이 하나도 로딩되지 않음"
        # 일부 관계는 추상 타입 참조로 스킵될 수 있으므로
        # 전체 RELATIONSHIP_TYPES 수보다 적을 수 있음
        assert link_count >= 70, f"LinkType 수가 너무 적음: {link_count} (70개 이상 기대)"

    def test_validate_passes(self) -> None:
        """TC-C04: 로딩 후 ontology.validate()가 통과해야 한다."""
        ontology = load_maritime_ontology()
        is_valid, errors = ontology.validate()
        assert is_valid is True, f"Ontology 검증 실패: {errors[:5]}"

    def test_export_to_cypher(self) -> None:
        """TC-C05: export_ontology_to_cypher() 반환 문자열에 Cypher 구문 포함."""
        ontology = load_maritime_ontology()
        cypher = export_ontology_to_cypher(ontology)

        assert isinstance(cypher, str), "반환 타입이 str이 아님"
        assert len(cypher) > 0, "빈 문자열 반환"
        assert "CREATE CONSTRAINT" in cypher, "CREATE CONSTRAINT 구문 미포함"
        assert "CREATE INDEX" in cypher, "CREATE INDEX 구문 미포함"

    def test_get_schema_for_llm(self) -> None:
        """TC-C06: get_schema_for_llm() 반환 문자열에 주요 섹션 포함."""
        schema = get_schema_for_llm()

        assert isinstance(schema, str), "반환 타입이 str이 아님"
        assert len(schema) > 100, "스키마 출력이 너무 짧음"
        assert "Entity Types" in schema, "Entity Types 섹션 미포함"
        assert "Relationships" in schema, "Relationships 섹션 미포함"
        assert "Vessel" in schema, "Vessel 엔티티 미포함"

    def test_get_schema_for_llm_with_ontology(self) -> None:
        """TC-C06-b: get_schema_for_llm(ontology) 인자 전달 시 정상 동작."""
        ontology = load_maritime_ontology()
        schema = get_schema_for_llm(ontology)
        assert "Vessel" in schema

    def test_loaded_vessel_has_properties(self) -> None:
        """TC-C02-b: 로딩된 Vessel ObjectType에 프로퍼티가 있어야 한다."""
        ontology = load_maritime_ontology()
        vessel = ontology.get_object_type("Vessel")
        assert vessel is not None, "Vessel ObjectType이 로딩되지 않음"
        assert len(vessel.properties) > 0, "Vessel에 프로퍼티가 없음"
        assert "mmsi" in vessel.properties, "Vessel에 mmsi 프로퍼티가 없음"

    def test_loaded_link_types_have_correct_endpoints(self) -> None:
        """TC-C03-b: 로딩된 LinkType의 from_type/to_type이 유효한 ObjectType."""
        ontology = load_maritime_ontology()
        for lt in ontology.get_all_link_types():
            assert ontology.get_object_type(lt.from_type) is not None, (
                f"LinkType '{lt.name}'의 from_type '{lt.from_type}'이 존재하지 않음"
            )
            assert ontology.get_object_type(lt.to_type) is not None, (
                f"LinkType '{lt.name}'의 to_type '{lt.to_type}'이 존재하지 않음"
            )
