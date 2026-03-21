"""KGConsistencyChecker 단위 테스트.

TC-C01 ~ TC-C04: kg/consistency/ 패키지의 SchemaDefinition, ConsistencyCheck,
built-in 체크 클래스, KGConsistencyChecker 오케스트레이터 검증.
모든 테스트는 Neo4j 없이 순수 Python으로 동작한다.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from kg.consistency import KGConsistencyChecker
from kg.consistency.checks import (
    CardinalityCheck,
    ConsistencyCheck,
    DanglingRelationshipCheck,
    EnumValueCheck,
    LabelSchema,
    OrphanNodeCheck,
    PropertySchema,
    PropertyTypeCheck,
    RequiredPropertyCheck,
    SchemaAlignmentCheck,
    SchemaDefinition,
)
from kg.quality_gate import CheckStatus, GateReport


# ---------------------------------------------------------------------------
# 공통 헬퍼 팩토리
# ---------------------------------------------------------------------------


def _valid_schema() -> SchemaDefinition:
    """유효한 스키마 정의를 반환한다."""
    return SchemaDefinition(
        labels={
            "Vessel": LabelSchema(
                properties={
                    "vesselType": PropertySchema(
                        expected_type="str",
                        enum_values=frozenset({"CARGO", "TANKER", "PASSENGER"}),
                    ),
                    "mmsi": PropertySchema(expected_type="str"),
                },
                required_properties=frozenset({"mmsi"}),
            ),
            "Port": LabelSchema(
                properties={
                    "name": PropertySchema(expected_type="str"),
                },
                required_properties=frozenset({"name"}),
            ),
        },
        relationship_types=frozenset({"DOCKED_AT", "OPERATED_BY"}),
    )


def _empty_schema() -> SchemaDefinition:
    """레이블이 없는 빈 스키마를 반환한다."""
    return SchemaDefinition()


# =============================================================================
# TC-C01: Schema 모델 데이터클래스 검증
# =============================================================================


@pytest.mark.unit
class TestSchemaModels:
    """PropertySchema, LabelSchema, SchemaDefinition 데이터클래스 검증."""

    def test_property_schema_defaults(self) -> None:
        """TC-C01-a: PropertySchema 기본값 확인."""
        ps = PropertySchema(expected_type="str")
        assert ps.min_cardinality == 0
        assert ps.max_cardinality is None
        assert ps.enum_values is None

    def test_property_schema_with_enum(self) -> None:
        """TC-C01-b: enum_values가 있는 PropertySchema 생성."""
        ps = PropertySchema(
            expected_type="str",
            enum_values=frozenset({"CARGO", "TANKER"}),
        )
        assert "CARGO" in ps.enum_values
        assert "TANKER" in ps.enum_values

    def test_property_schema_cardinality(self) -> None:
        """TC-C01-c: min/max_cardinality가 설정된 PropertySchema."""
        ps = PropertySchema(expected_type="int", min_cardinality=1, max_cardinality=5)
        assert ps.min_cardinality == 1
        assert ps.max_cardinality == 5

    def test_label_schema_defaults(self) -> None:
        """TC-C01-d: LabelSchema 기본값 — 빈 properties와 required_properties."""
        ls = LabelSchema()
        assert ls.properties == {}
        assert ls.required_properties == frozenset()

    def test_label_schema_with_data(self) -> None:
        """TC-C01-e: properties와 required_properties가 있는 LabelSchema."""
        ls = LabelSchema(
            properties={"mmsi": PropertySchema(expected_type="str")},
            required_properties=frozenset({"mmsi"}),
        )
        assert "mmsi" in ls.properties
        assert "mmsi" in ls.required_properties

    def test_schema_definition_defaults(self) -> None:
        """TC-C01-f: SchemaDefinition 기본값 — 빈 labels와 relationship_types."""
        sd = SchemaDefinition()
        assert sd.labels == {}
        assert sd.relationship_types == frozenset()

    def test_schema_definition_with_data(self) -> None:
        """TC-C01-g: labels와 relationship_types가 있는 SchemaDefinition."""
        sd = _valid_schema()
        assert "Vessel" in sd.labels
        assert "Port" in sd.labels
        assert "DOCKED_AT" in sd.relationship_types

    def test_property_schema_frozen(self) -> None:
        """TC-C01-h: PropertySchema는 frozen — 속성 할당 시 FrozenInstanceError."""
        ps = PropertySchema(expected_type="str")
        with pytest.raises(FrozenInstanceError):
            ps.expected_type = "int"  # type: ignore[misc]

    def test_label_schema_frozen(self) -> None:
        """TC-C01-i: LabelSchema는 frozen — 속성 할당 시 FrozenInstanceError."""
        ls = LabelSchema()
        with pytest.raises(FrozenInstanceError):
            ls.required_properties = frozenset({"x"})  # type: ignore[misc]

    def test_schema_definition_frozen(self) -> None:
        """TC-C01-j: SchemaDefinition는 frozen — 속성 할당 시 FrozenInstanceError."""
        sd = SchemaDefinition()
        with pytest.raises(FrozenInstanceError):
            sd.relationship_types = frozenset({"X"})  # type: ignore[misc]


# =============================================================================
# TC-C02: SchemaAlignmentCheck (오프라인) 검증
# =============================================================================


@pytest.mark.unit
class TestSchemaAlignmentCheck:
    """SchemaAlignmentCheck 오프라인 스키마 구조 검증."""

    def test_valid_schema_passes(self) -> None:
        """TC-C02-a: 올바른 스키마는 PASSED 결과를 반환한다."""
        check = SchemaAlignmentCheck()
        result = check.check(_valid_schema())
        assert result.status == CheckStatus.PASSED

    def test_empty_schema_passes(self) -> None:
        """TC-C02-b: 빈 스키마도 PASSED이다 (검증 대상이 없음)."""
        check = SchemaAlignmentCheck()
        result = check.check(_empty_schema())
        assert result.status == CheckStatus.PASSED

    def test_empty_label_name_fails(self) -> None:
        """TC-C02-c: 빈 문자열 레이블 이름은 FAILED를 반환한다."""
        schema = SchemaDefinition(
            labels={
                "": LabelSchema(
                    properties={"name": PropertySchema(expected_type="str")},
                ),
            }
        )
        check = SchemaAlignmentCheck()
        result = check.check(schema)
        assert result.status == CheckStatus.FAILED

    def test_whitespace_label_name_fails(self) -> None:
        """TC-C02-d: 공백만 있는 레이블 이름도 FAILED이다."""
        schema = SchemaDefinition(
            labels={"   ": LabelSchema()}
        )
        check = SchemaAlignmentCheck()
        result = check.check(schema)
        assert result.status == CheckStatus.FAILED

    def test_required_property_not_defined_fails(self) -> None:
        """TC-C02-e: required_properties에 정의되지 않은 프로퍼티가 있으면 FAILED이다."""
        schema = SchemaDefinition(
            labels={
                "Vessel": LabelSchema(
                    properties={"name": PropertySchema(expected_type="str")},
                    required_properties=frozenset({"name", "undefinedProp"}),
                ),
            }
        )
        check = SchemaAlignmentCheck()
        result = check.check(schema)
        assert result.status == CheckStatus.FAILED
        assert "undefinedProp" in str(result.details)

    def test_empty_enum_values_fails(self) -> None:
        """TC-C02-f: enum_values가 빈 frozenset이면 FAILED이다."""
        schema = SchemaDefinition(
            labels={
                "Vessel": LabelSchema(
                    properties={
                        "vesselType": PropertySchema(
                            expected_type="str",
                            enum_values=frozenset(),  # 빈 enum
                        ),
                    }
                ),
            }
        )
        check = SchemaAlignmentCheck()
        result = check.check(schema)
        assert result.status == CheckStatus.FAILED

    def test_negative_cardinality_fails(self) -> None:
        """TC-C02-g: min_cardinality < 0이면 FAILED이다."""
        schema = SchemaDefinition(
            labels={
                "Vessel": LabelSchema(
                    properties={
                        "name": PropertySchema(
                            expected_type="str",
                            min_cardinality=-1,
                        ),
                    }
                ),
            }
        )
        check = SchemaAlignmentCheck()
        result = check.check(schema)
        assert result.status == CheckStatus.FAILED

    def test_max_less_than_min_fails(self) -> None:
        """TC-C02-h: max_cardinality < min_cardinality이면 FAILED이다."""
        schema = SchemaDefinition(
            labels={
                "Vessel": LabelSchema(
                    properties={
                        "name": PropertySchema(
                            expected_type="str",
                            min_cardinality=5,
                            max_cardinality=2,
                        ),
                    }
                ),
            }
        )
        check = SchemaAlignmentCheck()
        result = check.check(schema)
        assert result.status == CheckStatus.FAILED

    def test_max_equal_min_passes(self) -> None:
        """TC-C02-i: max_cardinality == min_cardinality는 유효하다."""
        schema = SchemaDefinition(
            labels={
                "Vessel": LabelSchema(
                    properties={
                        "name": PropertySchema(
                            expected_type="str",
                            min_cardinality=1,
                            max_cardinality=1,
                        ),
                    }
                ),
            }
        )
        check = SchemaAlignmentCheck()
        result = check.check(schema)
        assert result.status == CheckStatus.PASSED

    def test_no_neo4j_needed(self) -> None:
        """TC-C02-j: SchemaAlignmentCheck는 requires_connection이 False이다."""
        check = SchemaAlignmentCheck()
        assert check.requires_connection is False

    def test_check_name(self) -> None:
        """TC-C02-k: SchemaAlignmentCheck의 name은 'schema_alignment'이다."""
        check = SchemaAlignmentCheck()
        assert check.name == "schema_alignment"

    def test_failed_details_contain_issues(self) -> None:
        """TC-C02-l: FAILED 결과의 details에는 'issues' 키가 있다."""
        schema = SchemaDefinition(labels={"": LabelSchema()})
        check = SchemaAlignmentCheck()
        result = check.check(schema)
        assert result.status == CheckStatus.FAILED
        assert "issues" in result.details
        assert len(result.details["issues"]) > 0


# =============================================================================
# TC-C03: 온라인 체크 — session=None일 때 SKIPPED
# =============================================================================


@pytest.mark.unit
class TestOnlineChecksSkipped:
    """온라인 체크들은 session=None일 때 SKIPPED를 반환한다."""

    def test_property_type_check_skipped(self) -> None:
        """TC-C03-a: PropertyTypeCheck는 session=None이면 SKIPPED이다."""
        check = PropertyTypeCheck()
        result = check.check(_valid_schema(), session=None)
        assert result.status == CheckStatus.SKIPPED

    def test_required_property_check_skipped(self) -> None:
        """TC-C03-b: RequiredPropertyCheck는 session=None이면 SKIPPED이다."""
        check = RequiredPropertyCheck()
        result = check.check(_valid_schema(), session=None)
        assert result.status == CheckStatus.SKIPPED

    def test_enum_value_check_skipped(self) -> None:
        """TC-C03-c: EnumValueCheck는 session=None이면 SKIPPED이다."""
        check = EnumValueCheck()
        result = check.check(_valid_schema(), session=None)
        assert result.status == CheckStatus.SKIPPED

    def test_cardinality_check_skipped(self) -> None:
        """TC-C03-d: CardinalityCheck는 session=None이면 SKIPPED이다."""
        check = CardinalityCheck()
        result = check.check(_valid_schema(), session=None)
        assert result.status == CheckStatus.SKIPPED

    def test_orphan_node_check_skipped(self) -> None:
        """TC-C03-e: OrphanNodeCheck는 session=None이면 SKIPPED이다."""
        check = OrphanNodeCheck()
        result = check.check(_valid_schema(), session=None)
        assert result.status == CheckStatus.SKIPPED

    def test_dangling_relationship_check_skipped(self) -> None:
        """TC-C03-f: DanglingRelationshipCheck는 session=None이면 SKIPPED이다."""
        check = DanglingRelationshipCheck()
        result = check.check(_valid_schema(), session=None)
        assert result.status == CheckStatus.SKIPPED

    def test_all_online_checks_require_connection(self) -> None:
        """TC-C03-g: 온라인 체크들은 모두 requires_connection == True이다."""
        online_checks: list[ConsistencyCheck] = [
            PropertyTypeCheck(),
            RequiredPropertyCheck(),
            EnumValueCheck(),
            CardinalityCheck(),
            OrphanNodeCheck(),
            DanglingRelationshipCheck(),
        ]
        for check in online_checks:
            assert check.requires_connection is True, (
                f"{check.__class__.__name__}.requires_connection should be True"
            )

    def test_skipped_result_has_reason(self) -> None:
        """TC-C03-h: SKIPPED 결과의 details에는 'reason' 키가 있다."""
        check = PropertyTypeCheck()
        result = check.check(_valid_schema(), session=None)
        assert "reason" in result.details

    def test_online_check_names(self) -> None:
        """TC-C03-i: 각 온라인 체크의 name이 올바르다."""
        assert PropertyTypeCheck().name == "property_type"
        assert RequiredPropertyCheck().name == "required_property"
        assert EnumValueCheck().name == "enum_value"
        assert CardinalityCheck().name == "cardinality"
        assert OrphanNodeCheck().name == "orphan_node"
        assert DanglingRelationshipCheck().name == "dangling_relationship"


# =============================================================================
# TC-C04: KGConsistencyChecker 오케스트레이터 검증
# =============================================================================


@pytest.mark.unit
class TestKGConsistencyChecker:
    """KGConsistencyChecker 체크 등록, 실행, 결과 집계 검증."""

    def test_default_7_checks(self) -> None:
        """TC-C04-a: 기본 체크 목록에는 7개의 체크가 있다."""
        checker = KGConsistencyChecker(_valid_schema())
        assert len(checker._checks) == 7

    def test_check_names(self) -> None:
        """TC-C04-b: check_names 프로퍼티는 체크 이름 리스트를 반환한다."""
        checker = KGConsistencyChecker(_valid_schema())
        names = checker.check_names
        assert "schema_alignment" in names
        assert "property_type" in names
        assert "required_property" in names
        assert "enum_value" in names
        assert "cardinality" in names
        assert "orphan_node" in names
        assert "dangling_relationship" in names

    def test_check_names_order(self) -> None:
        """TC-C04-c: check_names는 등록 순서를 유지한다."""
        checker = KGConsistencyChecker(_valid_schema())
        names = checker.check_names
        # schema_alignment가 첫 번째이어야 함
        assert names[0] == "schema_alignment"

    def test_add_check_fluent(self) -> None:
        """TC-C04-d: add_check()는 self를 반환하여 체이닝이 가능하다."""
        checker = KGConsistencyChecker(_valid_schema())
        returned = checker.add_check(SchemaAlignmentCheck())
        assert returned is checker

    def test_add_check_increases_count(self) -> None:
        """TC-C04-e: add_check() 호출 후 체크 수가 하나 증가한다."""
        checker = KGConsistencyChecker(_valid_schema())
        initial_count = len(checker._checks)
        checker.add_check(SchemaAlignmentCheck())
        assert len(checker._checks) == initial_count + 1

    def test_run_offline_returns_gate_report(self) -> None:
        """TC-C04-f: run_offline()은 GateReport를 반환한다."""
        checker = KGConsistencyChecker(_valid_schema())
        report = checker.run_offline()
        assert isinstance(report, GateReport)

    def test_run_offline_only_offline_checks(self) -> None:
        """TC-C04-g: run_offline()은 connection이 불필요한 체크만 실행한다."""
        checker = KGConsistencyChecker(_valid_schema())
        report = checker.run_offline()
        # 기본 7개 중 오프라인 체크는 1개 (SchemaAlignmentCheck)
        assert len(report.checks) == 1
        assert report.checks[0].name == "schema_alignment"

    def test_run_offline_valid_schema_passes(self) -> None:
        """TC-C04-h: 유효한 스키마로 run_offline() 실행 시 report.passed == True이다."""
        checker = KGConsistencyChecker(_valid_schema())
        report = checker.run_offline()
        assert report.passed is True

    def test_run_offline_invalid_schema_fails(self) -> None:
        """TC-C04-i: 잘못된 스키마로 run_offline() 실행 시 report.passed == False이다."""
        bad_schema = SchemaDefinition(
            labels={
                "Vessel": LabelSchema(
                    properties={"name": PropertySchema(expected_type="str")},
                    required_properties=frozenset({"name", "nonExistent"}),
                ),
            }
        )
        checker = KGConsistencyChecker(bad_schema)
        report = checker.run_offline()
        assert report.passed is False

    def test_run_checks_by_name(self) -> None:
        """TC-C04-j: run_checks(['schema_alignment'])은 해당 체크만 실행한다."""
        checker = KGConsistencyChecker(_valid_schema())
        report = checker.run_checks(["schema_alignment"])
        assert len(report.checks) == 1
        assert report.checks[0].name == "schema_alignment"

    def test_run_checks_multiple_names(self) -> None:
        """TC-C04-k: run_checks(['schema_alignment', 'property_type'])은 두 체크를 실행한다."""
        checker = KGConsistencyChecker(_valid_schema())
        report = checker.run_checks(["schema_alignment", "property_type"])
        assert len(report.checks) == 2

    def test_run_checks_unknown_name_ignored(self) -> None:
        """TC-C04-l: 존재하지 않는 체크명은 경고 로그 후 무시된다 (크래시 없음)."""
        checker = KGConsistencyChecker(_valid_schema())
        # 알 수 없는 이름이 포함된 경우 예외 없이 실행되어야 함
        report = checker.run_checks(["schema_alignment", "nonexistent_check_xyz"])
        # schema_alignment만 실행됨
        assert len(report.checks) == 1
        assert report.checks[0].name == "schema_alignment"

    def test_run_checks_empty_list(self) -> None:
        """TC-C04-m: 빈 이름 리스트로 run_checks() 실행 시 빈 report가 반환된다."""
        checker = KGConsistencyChecker(_valid_schema())
        report = checker.run_checks([])
        assert len(report.checks) == 0

    def test_schema_property(self) -> None:
        """TC-C04-n: checker.schema는 생성 시 전달한 스키마를 반환한다."""
        schema = _valid_schema()
        checker = KGConsistencyChecker(schema)
        assert checker.schema is schema

    def test_custom_checks_list(self) -> None:
        """TC-C04-o: checks 파라미터로 커스텀 체크 목록을 지정할 수 있다."""
        custom_checks: list[ConsistencyCheck] = [SchemaAlignmentCheck()]
        checker = KGConsistencyChecker(_valid_schema(), checks=custom_checks)
        assert len(checker._checks) == 1
        assert checker._checks[0].name == "schema_alignment"

    def test_gate_report_passed_with_only_skipped(self) -> None:
        """TC-C04-p: SKIPPED 결과만 있으면 report.passed == True이다."""
        # 온라인 체크만 포함한 체커를 session=None으로 실행
        checker = KGConsistencyChecker(
            _valid_schema(),
            checks=[PropertyTypeCheck(), RequiredPropertyCheck()],
        )
        report = checker.run_checks(
            ["property_type", "required_property"],
            session=None,
        )
        # 모두 SKIPPED이면 passed는 True (FAILED가 없음)
        assert report.passed is True
        for result in report.checks:
            assert result.status == CheckStatus.SKIPPED

    def test_run_offline_with_only_online_checks(self) -> None:
        """TC-C04-q: 오프라인 체크가 없는 checker에서 run_offline() 실행 시 빈 report."""
        checker = KGConsistencyChecker(
            _valid_schema(),
            checks=[PropertyTypeCheck()],  # online only
        )
        report = checker.run_offline()
        assert len(report.checks) == 0
        assert report.passed is True  # FAILED 없음

    def test_consistency_check_abstract(self) -> None:
        """TC-C04-r: ConsistencyCheck는 추상 클래스 — 직접 인스턴스화 불가."""
        with pytest.raises(TypeError):
            ConsistencyCheck()  # type: ignore[abstract]
