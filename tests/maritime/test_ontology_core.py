"""Ontology Core 단위 테스트.

TC-A01 ~ TC-A10: kg/ontology/core.py의 ObjectType, LinkType, Ontology 클래스 검증.
모든 테스트는 Neo4j 없이 순수 Python으로 동작한다.
"""

from __future__ import annotations

import pytest

from kg.ontology.core import (
    Cardinality,
    FunctionDefinition,
    FunctionRegistry,
    LinkType,
    LinkTypeDefinition,
    ObjectType,
    ObjectTypeDefinition,
    Ontology,
    PropertyDefinition,
    PropertyType,
)

# =========================================================================
# TC-A01: ObjectType 생성
# =========================================================================


@pytest.mark.unit
class TestObjectTypeCreation:
    """ObjectType 생성 및 기본 속성 검증."""

    def test_object_type_name(self, sample_object_type_def: ObjectTypeDefinition) -> None:
        """TC-A01-a: ObjectType.name은 definition의 name과 동일해야 한다."""
        ot = ObjectType(sample_object_type_def)
        assert ot.name == "Vessel", f"Expected 'Vessel', got '{ot.name}'"

    def test_object_type_display_name(self, sample_object_type_def: ObjectTypeDefinition) -> None:
        """TC-A01-b: display_name이 설정되면 해당 값을 반환해야 한다."""
        ot = ObjectType(sample_object_type_def)
        assert ot.display_name == "선박", f"Expected '선박', got '{ot.display_name}'"

    def test_object_type_display_name_fallback(self) -> None:
        """TC-A01-c: display_name이 None이면 name을 반환해야 한다."""
        defn = ObjectTypeDefinition(name="Port")
        ot = ObjectType(defn)
        assert ot.display_name == "Port", "display_name 미설정 시 name 반환 필요"

    def test_object_type_description(self, sample_object_type_def: ObjectTypeDefinition) -> None:
        """TC-A01-d: description 속성 검증."""
        ot = ObjectType(sample_object_type_def)
        assert ot.description is not None
        assert "watercraft" in ot.description.lower()


# =========================================================================
# TC-A02: ObjectType 프로퍼티 조회
# =========================================================================


@pytest.mark.unit
class TestObjectTypeProperties:
    """ObjectType 프로퍼티 조회 검증."""

    def test_get_existing_property(self, sample_object_type_def: ObjectTypeDefinition) -> None:
        """TC-A02-a: 존재하는 프로퍼티 조회 시 PropertyDefinition 반환."""
        ot = ObjectType(sample_object_type_def)
        prop = ot.get_property("mmsi")
        assert prop is not None, "mmsi 프로퍼티가 존재해야 한다"
        assert prop.type == PropertyType.INTEGER

    def test_get_nonexistent_property(self, sample_object_type_def: ObjectTypeDefinition) -> None:
        """TC-A02-b: 존재하지 않는 프로퍼티 조회 시 None 반환."""
        ot = ObjectType(sample_object_type_def)
        prop = ot.get_property("nonExistent")
        assert prop is None, "존재하지 않는 프로퍼티는 None이어야 한다"

    def test_properties_dict(self, sample_object_type_def: ObjectTypeDefinition) -> None:
        """TC-A02-c: properties 딕셔너리에 모든 정의된 프로퍼티가 존재."""
        ot = ObjectType(sample_object_type_def)
        expected_keys = {"mmsi", "name", "vesselType", "grossTonnage", "flag"}
        assert set(ot.properties.keys()) == expected_keys


# =========================================================================
# TC-A03: ObjectType Primary Key
# =========================================================================


@pytest.mark.unit
class TestObjectTypePrimaryKey:
    """ObjectType Primary Key 검증."""

    def test_get_primary_key(self, sample_object_type_def: ObjectTypeDefinition) -> None:
        """TC-A03-a: primary_key=True로 지정된 프로퍼티를 반환."""
        ot = ObjectType(sample_object_type_def)
        pk = ot.get_primary_key()
        assert pk == "mmsi", f"Primary key should be 'mmsi', got '{pk}'"

    def test_no_primary_key(self) -> None:
        """TC-A03-b: PK가 없는 ObjectType에서는 None 반환."""
        defn = ObjectTypeDefinition(
            name="SimpleType",
            properties={
                "id": PropertyDefinition(type=PropertyType.STRING),
            },
        )
        ot = ObjectType(defn)
        assert ot.get_primary_key() is None


# =========================================================================
# TC-A04: ObjectType Required Properties
# =========================================================================


@pytest.mark.unit
class TestObjectTypeRequiredProperties:
    """Required properties 검증."""

    def test_get_required_properties(self, sample_object_type_def: ObjectTypeDefinition) -> None:
        """TC-A04: required=True인 프로퍼티만 반환되어야 한다."""
        ot = ObjectType(sample_object_type_def)
        required = ot.get_required_properties()
        assert "mmsi" in required, "mmsi는 required여야 한다"
        assert "name" in required, "name은 required여야 한다"
        assert "vesselType" not in required, "vesselType은 required가 아니다"
        assert len(required) == 2, f"Expected 2 required properties, got {len(required)}"


# =========================================================================
# TC-A05: ObjectType 데이터 유효성 검증
# =========================================================================


@pytest.mark.unit
class TestObjectTypeValidation:
    """ObjectType.validate() 메서드 검증."""

    def test_valid_data(self, sample_object_type_def: ObjectTypeDefinition) -> None:
        """TC-A05-a: 필수 필드가 모두 있으면 유효."""
        ot = ObjectType(sample_object_type_def)
        is_valid, errors = ot.validate({"mmsi": 440123001, "name": "테스트선"})
        assert is_valid is True, f"유효한 데이터인데 실패: {errors}"
        assert len(errors) == 0

    def test_missing_required_field(self, sample_object_type_def: ObjectTypeDefinition) -> None:
        """TC-A05-b: 필수 필드 누락 시 에러."""
        ot = ObjectType(sample_object_type_def)
        is_valid, errors = ot.validate({"mmsi": 440123001})  # name 누락
        assert is_valid is False, "name 누락 시 유효하지 않아야 한다"
        assert any("name" in e for e in errors), "name 관련 에러가 있어야 한다"

    def test_enum_violation(self, sample_object_type_def: ObjectTypeDefinition) -> None:
        """TC-A05-c: enum_values 위반 시 에러."""
        ot = ObjectType(sample_object_type_def)
        is_valid, errors = ot.validate(
            {
                "mmsi": 440123001,
                "name": "테스트선",
                "vesselType": "InvalidType",
            }
        )
        assert is_valid is False, "enum 위반 시 유효하지 않아야 한다"
        assert any("vesselType" in e for e in errors)

    def test_min_length_violation(self, sample_object_type_def: ObjectTypeDefinition) -> None:
        """TC-A05-d: min_length 위반 시 에러."""
        ot = ObjectType(sample_object_type_def)
        is_valid, errors = ot.validate(
            {
                "mmsi": 440123001,
                "name": "테스트선",
                "flag": "K",  # min_length=2인데 1자
            }
        )
        assert is_valid is False, "min_length 위반 시 유효하지 않아야 한다"

    def test_extra_properties_allowed(self, sample_object_type_def: ObjectTypeDefinition) -> None:
        """TC-A05-e: 정의되지 않은 추가 프로퍼티는 허용."""
        ot = ObjectType(sample_object_type_def)
        is_valid, errors = ot.validate(
            {
                "mmsi": 440123001,
                "name": "테스트선",
                "extraField": "allowed",
            }
        )
        assert is_valid is True, f"추가 프로퍼티는 허용되어야 한다: {errors}"


# =========================================================================
# TC-A06: ObjectType export (to_dict)
# =========================================================================


@pytest.mark.unit
class TestObjectTypeExport:
    """ObjectType.to_dict() 직렬화 검증."""

    def test_to_dict_structure(self, sample_object_type_def: ObjectTypeDefinition) -> None:
        """TC-A06-a: to_dict() 반환 딕셔너리 구조 검증."""
        ot = ObjectType(sample_object_type_def)
        d = ot.to_dict()

        assert d["name"] == "Vessel"
        assert d["displayName"] == "선박"
        assert "description" in d
        assert "properties" in d
        assert "interfaces" in d

    def test_to_dict_properties(self, sample_object_type_def: ObjectTypeDefinition) -> None:
        """TC-A06-b: to_dict() 내 properties 직렬화 검증."""
        ot = ObjectType(sample_object_type_def)
        d = ot.to_dict()
        props = d["properties"]

        assert "mmsi" in props
        assert props["mmsi"]["type"] == "INTEGER"
        assert props["mmsi"]["primaryKey"] is True
        assert props["mmsi"]["required"] is True


# =========================================================================
# TC-A07: LinkType 생성 및 속성
# =========================================================================


@pytest.mark.unit
class TestLinkType:
    """LinkType 생성 및 속성 검증."""

    def test_link_type_creation(self, sample_link_type_def: LinkTypeDefinition) -> None:
        """TC-A07-a: LinkType 생성 후 속성 검증."""
        lt = LinkType(sample_link_type_def)
        assert lt.name == "DOCKED_AT"
        assert lt.from_type == "Vessel"
        assert lt.to_type == "Berth"
        assert lt.cardinality == "MANY_TO_ONE"

    def test_link_type_description(self, sample_link_type_def: LinkTypeDefinition) -> None:
        """TC-A07-b: LinkType description 검증."""
        lt = LinkType(sample_link_type_def)
        assert lt.description is not None
        assert "docked" in lt.description.lower()

    def test_link_type_properties(self, sample_link_type_def: LinkTypeDefinition) -> None:
        """TC-A07-c: LinkType 프로퍼티 검증."""
        lt = LinkType(sample_link_type_def)
        assert "since" in lt.properties
        assert "until" in lt.properties

    def test_link_type_to_dict(self, sample_link_type_def: LinkTypeDefinition) -> None:
        """TC-A07-d: LinkType.to_dict() 구조 검증."""
        lt = LinkType(sample_link_type_def)
        d = lt.to_dict()
        assert d["name"] == "DOCKED_AT"
        assert d["fromType"] == "Vessel"
        assert d["toType"] == "Berth"
        assert "cardinality" in d
        assert "properties" in d

    def test_link_type_cardinality_enum(self) -> None:
        """TC-A07-e: Cardinality enum 값 처리 검증."""
        defn = LinkTypeDefinition(
            name="TEST_REL",
            from_type="A",
            to_type="B",
            cardinality=Cardinality.ONE_TO_MANY,
        )
        lt = LinkType(defn)
        assert lt.cardinality == "ONE_TO_MANY"

    def test_link_type_cardinality_string(self) -> None:
        """TC-A07-f: Cardinality 문자열 값 처리 검증."""
        defn = LinkTypeDefinition(
            name="TEST_REL",
            from_type="A",
            to_type="B",
            cardinality="MANY_TO_MANY",
        )
        lt = LinkType(defn)
        assert lt.cardinality == "MANY_TO_MANY"


# =========================================================================
# TC-A08: Ontology 전체 검증
# =========================================================================


@pytest.mark.unit
class TestOntologyValidation:
    """Ontology.validate() 메서드 검증."""

    def test_valid_ontology(self, minimal_ontology: Ontology) -> None:
        """TC-A08-a: 올바르게 구성된 Ontology는 validate() 통과."""
        is_valid, errors = minimal_ontology.validate()
        assert is_valid is True, f"유효한 ontology인데 실패: {errors}"
        assert len(errors) == 0

    def test_ontology_name(self, minimal_ontology: Ontology) -> None:
        """TC-A08-b: Ontology 이름 검증."""
        assert minimal_ontology.name == "test"

    def test_get_object_type(self, minimal_ontology: Ontology) -> None:
        """TC-A08-c: get_object_type() 조회."""
        vessel = minimal_ontology.get_object_type("Vessel")
        assert vessel is not None
        assert vessel.name == "Vessel"

    def test_get_nonexistent_object_type(self, minimal_ontology: Ontology) -> None:
        """TC-A08-d: 존재하지 않는 ObjectType 조회 시 None."""
        result = minimal_ontology.get_object_type("NonExistent")
        assert result is None

    def test_get_all_object_types(self, minimal_ontology: Ontology) -> None:
        """TC-A08-e: get_all_object_types() 전체 목록."""
        all_types = minimal_ontology.get_all_object_types()
        assert len(all_types) == 2  # Vessel, Berth
        names = {ot.name for ot in all_types}
        assert names == {"Vessel", "Berth"}

    def test_get_link_types_for_object(self, minimal_ontology: Ontology) -> None:
        """TC-A08-f: get_link_types_for_object() outgoing/incoming 분류."""
        links = minimal_ontology.get_link_types_for_object("Vessel")
        assert len(links["outgoing"]) == 1, "Vessel의 outgoing 관계 1개 기대"
        assert links["outgoing"][0].name == "DOCKED_AT"
        assert len(links["incoming"]) == 0, "Vessel의 incoming 관계 0개 기대"

    def test_get_schema_summary(self, minimal_ontology: Ontology) -> None:
        """TC-A08-g: get_schema_summary() 출력 검증."""
        summary = minimal_ontology.get_schema_summary()
        assert "Ontology: test" in summary
        assert "Vessel" in summary
        assert "DOCKED_AT" in summary


# =========================================================================
# TC-A09: Ontology 중복 등록 거부
# =========================================================================


@pytest.mark.unit
class TestOntologyDuplicateRejection:
    """중복 정의 시 ValueError 발생 검증."""

    def test_duplicate_object_type(self) -> None:
        """TC-A09-a: 동일 이름 ObjectType 중복 등록 시 ValueError."""
        ontology = Ontology(name="test")
        ontology.define_object_type(ObjectTypeDefinition(name="Vessel"))

        with pytest.raises(ValueError, match="already exists"):
            ontology.define_object_type(ObjectTypeDefinition(name="Vessel"))

    def test_duplicate_link_type(self) -> None:
        """TC-A09-b: 동일 이름 LinkType 중복 등록 시 ValueError."""
        ontology = Ontology(name="test")
        ontology.define_object_type(ObjectTypeDefinition(name="A"))
        ontology.define_object_type(ObjectTypeDefinition(name="B"))
        ontology.define_link_type(
            LinkTypeDefinition(
                name="REL",
                from_type="A",
                to_type="B",
            )
        )

        with pytest.raises(ValueError, match="already exists"):
            ontology.define_link_type(
                LinkTypeDefinition(
                    name="REL",
                    from_type="A",
                    to_type="B",
                )
            )

    def test_link_type_unknown_from_type(self) -> None:
        """TC-A09-c: LinkType의 from_type이 존재하지 않으면 ValueError."""
        ontology = Ontology(name="test")
        ontology.define_object_type(ObjectTypeDefinition(name="B"))

        with pytest.raises(ValueError, match="does not exist"):
            ontology.define_link_type(
                LinkTypeDefinition(
                    name="REL",
                    from_type="NonExistent",
                    to_type="B",
                )
            )

    def test_link_type_unknown_to_type(self) -> None:
        """TC-A09-d: LinkType의 to_type이 존재하지 않으면 ValueError."""
        ontology = Ontology(name="test")
        ontology.define_object_type(ObjectTypeDefinition(name="A"))

        with pytest.raises(ValueError, match="does not exist"):
            ontology.define_link_type(
                LinkTypeDefinition(
                    name="REL",
                    from_type="A",
                    to_type="NonExistent",
                )
            )


# =========================================================================
# TC-A10: Ontology export
# =========================================================================


@pytest.mark.unit
class TestOntologyExport:
    """Ontology.export() 딕셔너리 구조 검증."""

    def test_export_keys(self, minimal_ontology: Ontology) -> None:
        """TC-A10-a: export() 반환 딕셔너리에 필수 키가 존재."""
        exported = minimal_ontology.export()
        expected_keys = {"name", "objectTypes", "linkTypes", "actions", "interfaces", "functions"}
        assert set(exported.keys()) == expected_keys

    def test_export_object_types(self, minimal_ontology: Ontology) -> None:
        """TC-A10-b: export()의 objectTypes 리스트 검증."""
        exported = minimal_ontology.export()
        ot_names = {ot["name"] for ot in exported["objectTypes"]}
        assert "Vessel" in ot_names
        assert "Berth" in ot_names

    def test_export_link_types(self, minimal_ontology: Ontology) -> None:
        """TC-A10-c: export()의 linkTypes 리스트 검증."""
        exported = minimal_ontology.export()
        lt_names = {lt["name"] for lt in exported["linkTypes"]}
        assert "DOCKED_AT" in lt_names

    def test_export_name(self, minimal_ontology: Ontology) -> None:
        """TC-A10-d: export()의 name 필드 검증."""
        exported = minimal_ontology.export()
        assert exported["name"] == "test"


# =========================================================================
# 추가: FunctionRegistry 테스트
# =========================================================================


@pytest.mark.unit
class TestFunctionRegistry:
    """FunctionRegistry 및 OntologyFunction 검증."""

    def test_register_and_get(self) -> None:
        """FunctionRegistry에 함수를 등록하고 조회."""
        registry = FunctionRegistry()
        defn = FunctionDefinition(
            name="calculate_distance",
            display_name="거리 계산",
            category="spatial",
            tags=["geo", "distance"],
        )
        func = registry.register(defn)
        assert func.name == "calculate_distance"
        assert registry.has("calculate_distance") is True
        assert registry.get("calculate_distance") is not None

    def test_duplicate_function_registration(self) -> None:
        """중복 함수 등록 시 ValueError."""
        registry = FunctionRegistry()
        defn = FunctionDefinition(name="func1")
        registry.register(defn)

        with pytest.raises(ValueError, match="already exists"):
            registry.register(FunctionDefinition(name="func1"))

    def test_remove_function(self) -> None:
        """함수 제거 검증."""
        registry = FunctionRegistry()
        registry.register(FunctionDefinition(name="func1"))
        assert registry.remove("func1") is True
        assert registry.has("func1") is False
        assert registry.remove("func1") is False  # 이미 제거됨

    def test_search_functions(self) -> None:
        """함수 검색 검증."""
        registry = FunctionRegistry()
        registry.register(FunctionDefinition(name="calc_dist", description="Calculate distance"))
        registry.register(FunctionDefinition(name="calc_speed", description="Calculate speed"))
        registry.register(FunctionDefinition(name="format_output", description="Format output"))

        results = registry.search("calc")
        assert len(results) == 2

        results = registry.search("distance")
        assert len(results) == 1
