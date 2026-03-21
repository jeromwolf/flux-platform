"""TemporalCypherBuilder 단위 테스트.

TC-T01 ~ TC-T13: kg/temporal/ 패키지의 TemporalRange 및 TemporalCypherBuilder 검증.
모든 테스트는 Neo4j 없이 순수 Python으로 동작한다.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from kg.temporal import TemporalCypherBuilder, TemporalMode, TemporalRange
from kg.temporal.builder import TemporalCypherBuilder as TemporalCypherBuilderDirect
from kg.temporal.models import TemporalMode as TemporalModeDirect
from kg.temporal.models import TemporalRange as TemporalRangeDirect


# =============================================================================
# TC-T01: TemporalRange 유효성 검증
# =============================================================================


@pytest.mark.unit
class TestTemporalRange:
    """TemporalRange 데이터클래스 생성 및 유효성 검증."""

    def test_default_mode_is_current(self) -> None:
        """TC-T01-a: 기본 mode는 CURRENT이어야 한다."""
        tr = TemporalRange()
        assert tr.mode == TemporalMode.CURRENT

    def test_range_requires_start_and_end(self) -> None:
        """TC-T01-b: RANGE 모드는 start와 end가 모두 필요하다."""
        with pytest.raises(ValueError, match="RANGE"):
            TemporalRange(
                start=datetime(2025, 1, 1),
                mode=TemporalMode.RANGE,
                # end 누락
            )

    def test_range_requires_start_no_end(self) -> None:
        """TC-T01-c: RANGE 모드에서 end만 없어도 ValueError가 발생한다."""
        with pytest.raises(ValueError):
            TemporalRange(
                end=datetime(2025, 12, 31),
                mode=TemporalMode.RANGE,
                # start 누락
            )

    def test_range_requires_both_raises(self) -> None:
        """TC-T01-d: RANGE 모드에서 start, end 둘 다 없으면 ValueError가 발생한다."""
        with pytest.raises(ValueError):
            TemporalRange(mode=TemporalMode.RANGE)

    def test_point_in_time_requires_start(self) -> None:
        """TC-T01-e: POINT_IN_TIME 모드는 start가 필요하다."""
        with pytest.raises(ValueError, match="POINT_IN_TIME"):
            TemporalRange(mode=TemporalMode.POINT_IN_TIME)

    def test_as_of_requires_start(self) -> None:
        """TC-T01-f: AS_OF 모드는 start가 필요하다."""
        with pytest.raises(ValueError, match="AS_OF"):
            TemporalRange(mode=TemporalMode.AS_OF)

    def test_history_mode_no_validation(self) -> None:
        """TC-T01-g: HISTORY 모드는 start/end 없이도 유효하다."""
        tr = TemporalRange(mode=TemporalMode.HISTORY)
        assert tr.mode == TemporalMode.HISTORY
        assert tr.start is None
        assert tr.end is None

    def test_current_mode_no_start_needed(self) -> None:
        """TC-T01-h: CURRENT 모드는 start 없이도 유효하다."""
        tr = TemporalRange(mode=TemporalMode.CURRENT)
        assert tr.mode == TemporalMode.CURRENT

    def test_custom_properties(self) -> None:
        """TC-T01-i: valid_from_property, valid_to_property가 올바르게 저장된다."""
        tr = TemporalRange(
            mode=TemporalMode.HISTORY,
            valid_from_property="startDate",
            valid_to_property="endDate",
        )
        assert tr.valid_from_property == "startDate"
        assert tr.valid_to_property == "endDate"

    def test_default_property_names(self) -> None:
        """TC-T01-j: 기본 프로퍼티명은 validFrom/validTo이다."""
        tr = TemporalRange()
        assert tr.valid_from_property == "validFrom"
        assert tr.valid_to_property == "validTo"

    def test_frozen(self) -> None:
        """TC-T01-k: TemporalRange는 frozen dataclass — 속성 할당 시 FrozenInstanceError."""
        tr = TemporalRange(mode=TemporalMode.HISTORY)
        with pytest.raises(FrozenInstanceError):
            tr.mode = TemporalMode.CURRENT  # type: ignore[misc]

    def test_valid_range_creation(self) -> None:
        """TC-T01-l: RANGE 모드에서 start, end 모두 제공 시 정상 생성."""
        tr = TemporalRange(
            start=datetime(2025, 1, 1),
            end=datetime(2025, 12, 31),
            mode=TemporalMode.RANGE,
        )
        assert tr.start == datetime(2025, 1, 1)
        assert tr.end == datetime(2025, 12, 31)

    def test_imports_from_models(self) -> None:
        """TC-T01-m: kg.temporal.models에서 직접 임포트도 동일 클래스이다."""
        assert TemporalRangeDirect is TemporalRange
        assert TemporalModeDirect is TemporalMode


# =============================================================================
# TC-T02: TemporalCypherBuilder 쿼리 생성
# =============================================================================


@pytest.mark.unit
class TestTemporalCypherBuilder:
    """TemporalCypherBuilder 쿼리 빌드 검증."""

    def test_at_time_generates_where_clauses(self) -> None:
        """TC-T02-a: at_time()은 validFrom <= $p 와 validTo IS NULL OR 조건을 생성한다."""
        t = datetime(2025, 6, 1, tzinfo=timezone.utc)
        query, params = (
            TemporalCypherBuilder()
            .match("(n:Vessel)")
            .at_time(t)
            .return_("n")
            .build()
        )
        assert "n.validFrom <=" in query, f"validFrom 조건 없음: {query}"
        assert "n.validTo IS NULL OR" in query, f"validTo IS NULL 조건 없음: {query}"
        assert len(params) == 1
        assert t in params.values()

    def test_between_generates_overlap_clauses(self) -> None:
        """TC-T02-b: between()은 Allen-interval 겹침 패턴을 생성한다."""
        start = datetime(2025, 1, 1)
        end = datetime(2025, 12, 31)
        query, params = (
            TemporalCypherBuilder()
            .match("(n:Route)")
            .between(start, end)
            .return_("n")
            .build()
        )
        # validFrom <= end_param AND (validTo IS NULL OR validTo >= start_param)
        assert "n.validFrom <=" in query
        assert "n.validTo IS NULL OR" in query
        assert len(params) == 2
        assert start in params.values()
        assert end in params.values()

    def test_current_generates_null_check(self) -> None:
        """TC-T02-c: current()은 validTo IS NULL OR 조건만 생성하고 validFrom 조건은 없다."""
        query, params = (
            TemporalCypherBuilder()
            .match("(n:Vessel)")
            .current()
            .return_("n")
            .build()
        )
        # CURRENT 모드 — validTo만 검사
        assert "n.validTo IS NULL OR" in query, f"validTo 조건 없음: {query}"
        assert len(params) == 1  # now 파라미터 하나

    def test_current_no_valid_from_check(self) -> None:
        """TC-T02-d: current()는 n.validFrom 조건을 추가하지 않는다."""
        query, _ = (
            TemporalCypherBuilder()
            .match("(n:Vessel)")
            .current()
            .return_("n")
            .build()
        )
        # WHERE 절에 n.validFrom <= 형태의 조건이 없어야 함
        assert "n.validFrom" not in query

    def test_with_history_no_temporal_clauses(self) -> None:
        """TC-T02-e: with_history()는 validFrom/validTo 조건을 추가하지 않는다."""
        query, params = (
            TemporalCypherBuilder()
            .match("(n:Vessel)")
            .with_history()
            .return_("n")
            .build()
        )
        assert "validFrom" not in query, f"HISTORY 모드에서 validFrom 조건이 있음: {query}"
        assert "validTo" not in query, f"HISTORY 모드에서 validTo 조건이 있음: {query}"
        assert len(params) == 0

    def test_as_of_same_as_at_time_pattern(self) -> None:
        """TC-T02-f: as_of()는 at_time()과 동일한 WHERE 패턴을 생성한다."""
        t = datetime(2025, 3, 15)

        query_at, params_at = (
            TemporalCypherBuilder()
            .match("(n:Vessel)")
            .at_time(t)
            .return_("n")
            .build()
        )
        query_asof, params_asof = (
            TemporalCypherBuilder()
            .match("(n:Vessel)")
            .as_of(t)
            .return_("n")
            .build()
        )
        # 파라미터 개수가 같아야 함
        assert len(params_at) == len(params_asof)
        # 두 쿼리 모두 validFrom <=, validTo IS NULL OR 포함
        assert "n.validFrom <=" in query_at
        assert "n.validFrom <=" in query_asof
        assert "n.validTo IS NULL OR" in query_at
        assert "n.validTo IS NULL OR" in query_asof

    def test_for_node_changes_alias(self) -> None:
        """TC-T02-g: for_node("v")는 쿼리에서 v.validFrom 등 올바른 별칭을 사용한다."""
        t = datetime(2025, 1, 1)
        query, _ = (
            TemporalCypherBuilder()
            .match("(v:Vessel)")
            .for_node("v")
            .at_time(t)
            .return_("v")
            .build()
        )
        assert "v.validFrom" in query, f"v.validFrom 없음: {query}"
        assert "v.validTo" in query, f"v.validTo 없음: {query}"
        assert "n.validFrom" not in query, "기본 별칭 n이 잘못 사용됨"

    def test_with_temporal_properties_custom(self) -> None:
        """TC-T02-h: with_temporal_properties()는 커스텀 프로퍼티명을 WHERE에 반영한다."""
        t = datetime(2025, 6, 1)
        query, _ = (
            TemporalCypherBuilder()
            .match("(e:Event)")
            .for_node("e")
            .with_temporal_properties("startDate", "endDate")
            .at_time(t)
            .return_("e")
            .build()
        )
        assert "e.startDate" in query, f"커스텀 validFrom 프로퍼티 없음: {query}"
        assert "e.endDate" in query, f"커스텀 validTo 프로퍼티 없음: {query}"

    def test_inherits_cypher_builder_match(self) -> None:
        """TC-T02-i: CypherBuilder의 match/where/return_ 등 메서드를 그대로 사용할 수 있다."""
        query, params = (
            TemporalCypherBuilder()
            .match("(v:Vessel)")
            .where("v.flag = $flag", {"flag": "KR"})
            .with_history()
            .return_("v")
            .build()
        )
        assert "MATCH (v:Vessel)" in query
        assert "v.flag = $flag" in query
        assert params["flag"] == "KR"

    def test_temporal_plus_regular_where(self) -> None:
        """TC-T02-j: 임시 조건과 일반 WHERE 조건이 AND로 결합된다."""
        t = datetime(2025, 1, 1)
        query, params = (
            TemporalCypherBuilder()
            .match("(v:Vessel)")
            .for_node("v")
            .where("v.flag = $flag", {"flag": "KR"})
            .at_time(t)
            .return_("v")
            .build()
        )
        assert "v.flag = $flag" in query
        assert "v.validFrom" in query
        assert "AND" in query
        assert params["flag"] == "KR"

    def test_parameters_no_collision(self) -> None:
        """TC-T02-k: 임시 파라미터명과 사용자 파라미터명이 충돌하지 않는다."""
        t = datetime(2025, 6, 1)
        _, params = (
            TemporalCypherBuilder()
            .match("(v:Vessel)")
            .where("v.mmsi = $mmsi", {"mmsi": "123456789"})
            .at_time(t)
            .return_("v")
            .build()
        )
        # 파라미터가 겹치지 않아야 함
        assert "mmsi" in params
        assert params["mmsi"] == "123456789"
        # 임시 파라미터(p1 등)도 별도로 존재
        temporal_params = {k: v for k, v in params.items() if k != "mmsi"}
        assert len(temporal_params) == 1
        assert t in temporal_params.values()

    def test_build_returns_tuple(self) -> None:
        """TC-T02-l: build()는 (str, dict) 튜플을 반환한다."""
        result = TemporalCypherBuilder().match("(n:Vessel)").with_history().return_("n").build()
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], str)
        assert isinstance(result[1], dict)

    def test_fluent_chaining(self) -> None:
        """TC-T02-m: 모든 설정 메서드가 self를 반환하여 체이닝이 가능하다."""
        builder = TemporalCypherBuilder()
        assert builder.for_node("v") is builder
        assert builder.with_temporal_properties("startDate", "endDate") is builder
        assert builder.with_history() is builder
        assert builder.match("(v:Vessel)") is builder
        assert builder.return_("v") is builder

    def test_at_time_fluent_returns_self(self) -> None:
        """TC-T02-n: at_time(), between(), current(), as_of()도 self를 반환한다."""
        t = datetime(2025, 1, 1)
        builder = TemporalCypherBuilder()
        assert builder.at_time(t) is builder

        builder2 = TemporalCypherBuilder()
        assert builder2.between(t, datetime(2025, 12, 31)) is builder2

        builder3 = TemporalCypherBuilder()
        assert builder3.current() is builder3

        builder4 = TemporalCypherBuilder()
        assert builder4.as_of(t) is builder4

    def test_imports_from_package(self) -> None:
        """TC-T02-o: kg.temporal 패키지에서 직접 임포트가 가능하다."""
        assert TemporalCypherBuilderDirect is TemporalCypherBuilder
