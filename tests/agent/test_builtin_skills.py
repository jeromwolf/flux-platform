"""Unit tests for built-in agent skills.

Covers:
    TC-BS01  create_builtin_skills returns non-empty registry
    TC-BS02  maritime_qa skill executes successfully
    TC-BS03  vessel_report skill executes successfully
"""

from __future__ import annotations

import json

import pytest

from agent.skills.builtins import (
    MARITIME_QA_SKILL,
    ROUTE_ANALYSIS_SKILL,
    VESSEL_REPORT_SKILL,
    create_builtin_skills,
)
from agent.skills.models import SkillDefinition, SkillResult
from agent.skills.registry import SkillRegistry


# ---------------------------------------------------------------------------
# TC-BS01: create_builtin_skills returns non-empty registry
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCreateBuiltinSkills:
    """TC-BS01: create_builtin_skills 팩토리 함수 검증."""

    def test_bs01a_returns_skill_registry(self) -> None:
        """TC-BS01-a: create_builtin_skills()가 SkillRegistry 인스턴스 반환."""
        registry = create_builtin_skills()
        assert isinstance(registry, SkillRegistry)

    def test_bs01b_registry_is_not_empty(self) -> None:
        """TC-BS01-b: 반환된 레지스트리가 하나 이상의 스킬을 포함."""
        registry = create_builtin_skills()
        assert registry.skill_count > 0

    def test_bs01c_all_expected_skills_registered(self) -> None:
        """TC-BS01-c: 3개 내장 스킬(maritime_qa, vessel_report, route_analysis)이 모두 등록됨."""
        expected = {"maritime_qa", "vessel_report", "route_analysis"}
        registry = create_builtin_skills()
        assert expected.issubset(set(registry.skill_names))

    def test_bs01d_skill_definitions_are_valid(self) -> None:
        """TC-BS01-d: 모든 스킬 정의가 SkillDefinition 인스턴스임."""
        registry = create_builtin_skills()
        for skill in registry.list_skills():
            assert isinstance(skill, SkillDefinition)

    def test_bs01e_skill_definitions_are_frozen(self) -> None:
        """TC-BS01-e: 스킬 정의들이 frozen dataclass임."""
        import dataclasses

        for defn in [MARITIME_QA_SKILL, VESSEL_REPORT_SKILL, ROUTE_ANALYSIS_SKILL]:
            with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
                defn.name = "changed"  # type: ignore[misc]

    def test_bs01f_all_skills_have_required_tools(self) -> None:
        """TC-BS01-f: 모든 스킬에 required_tools가 설정됨."""
        for defn in [MARITIME_QA_SKILL, VESSEL_REPORT_SKILL, ROUTE_ANALYSIS_SKILL]:
            assert len(defn.required_tools) > 0, f"{defn.name} has no required_tools"

    def test_bs01g_all_skills_have_maritime_category(self) -> None:
        """TC-BS01-g: 모든 내장 스킬의 category가 'maritime'임."""
        for defn in [MARITIME_QA_SKILL, VESSEL_REPORT_SKILL, ROUTE_ANALYSIS_SKILL]:
            assert defn.category == "maritime", f"{defn.name} category: {defn.category}"


# ---------------------------------------------------------------------------
# TC-BS02: maritime_qa skill executes successfully
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMaritimeQaSkill:
    """TC-BS02: maritime_qa 스킬 실행 검증."""

    def test_bs02a_maritime_qa_executes_successfully(self) -> None:
        """TC-BS02-a: maritime_qa 스킬이 성공적으로 실행됨."""
        registry = create_builtin_skills()
        result = registry.execute("maritime_qa", {"question": "부산항 수심은 얼마인가요?"})
        assert result.success is True

    def test_bs02b_maritime_qa_returns_skill_result(self) -> None:
        """TC-BS02-b: maritime_qa 실행 결과가 SkillResult 타입임."""
        registry = create_builtin_skills()
        result = registry.execute("maritime_qa", {"question": "선박 안전 규정"})
        assert isinstance(result, SkillResult)

    def test_bs02c_maritime_qa_output_is_json(self) -> None:
        """TC-BS02-c: maritime_qa 결과의 output이 JSON 파싱 가능함."""
        registry = create_builtin_skills()
        result = registry.execute("maritime_qa", {"question": "해상 기상 정보"})
        assert result.success is True
        data = json.loads(result.output)
        assert "question" in data

    def test_bs02d_maritime_qa_with_language_en(self) -> None:
        """TC-BS02-d: 영어 응답 요청(language=en) 처리."""
        registry = create_builtin_skills()
        result = registry.execute("maritime_qa", {
            "question": "What is the depth of Busan port?",
            "language": "en",
        })
        assert result.success is True
        data = json.loads(result.output)
        assert data.get("language") == "en"

    def test_bs02e_maritime_qa_steps_taken_positive(self) -> None:
        """TC-BS02-e: maritime_qa 실행 후 steps_taken > 0."""
        registry = create_builtin_skills()
        result = registry.execute("maritime_qa", {"question": "SOLAS 규정 요약"})
        assert result.steps_taken > 0

    def test_bs02f_maritime_qa_definition_has_required_params(self) -> None:
        """TC-BS02-f: maritime_qa 스킬 정의에 question 파라미터가 있음."""
        assert "question" in MARITIME_QA_SKILL.parameters


# ---------------------------------------------------------------------------
# TC-BS03: vessel_report skill executes successfully
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestVesselReportSkill:
    """TC-BS03: vessel_report 스킬 실행 검증."""

    def test_bs03a_vessel_report_executes_successfully(self) -> None:
        """TC-BS03-a: vessel_report 스킬이 성공적으로 실행됨."""
        registry = create_builtin_skills()
        result = registry.execute("vessel_report", {"vessel_query": "BUSAN PIONEER"})
        assert result.success is True

    def test_bs03b_vessel_report_returns_skill_result(self) -> None:
        """TC-BS03-b: vessel_report 실행 결과가 SkillResult 타입임."""
        registry = create_builtin_skills()
        result = registry.execute("vessel_report", {"vessel_query": "KOREA SPIRIT"})
        assert isinstance(result, SkillResult)

    def test_bs03c_vessel_report_output_is_json(self) -> None:
        """TC-BS03-c: vessel_report 결과의 output이 JSON 파싱 가능함."""
        registry = create_builtin_skills()
        result = registry.execute("vessel_report", {"vessel_query": "BUSAN"})
        assert result.success is True
        data = json.loads(result.output)
        assert "report_type" in data
        assert data["report_type"] == "vessel_status"

    def test_bs03d_vessel_report_contains_vessel_data(self) -> None:
        """TC-BS03-d: 보고서에 vessel 데이터가 포함됨."""
        registry = create_builtin_skills()
        result = registry.execute("vessel_report", {"vessel_query": "BUSAN PIONEER"})
        data = json.loads(result.output)
        assert "vessels" in data
        assert "vessel_count" in data

    def test_bs03e_vessel_report_steps_taken_positive(self) -> None:
        """TC-BS03-e: vessel_report 실행 후 steps_taken > 0."""
        registry = create_builtin_skills()
        result = registry.execute("vessel_report", {"vessel_query": "test"})
        assert result.steps_taken > 0

    def test_bs03f_route_analysis_skill_executes(self) -> None:
        """TC-BS03-f: route_analysis 스킬도 성공적으로 실행됨."""
        registry = create_builtin_skills()
        result = registry.execute("route_analysis", {
            "origin": "부산",
            "destination": "인천",
        })
        assert result.success is True

    def test_bs03g_route_analysis_output_is_json(self) -> None:
        """TC-BS03-g: route_analysis 결과의 output이 JSON 파싱 가능함."""
        registry = create_builtin_skills()
        result = registry.execute("route_analysis", {
            "origin": "부산",
            "destination": "인천",
        })
        data = json.loads(result.output)
        assert "report_type" in data
        assert data["report_type"] == "route_analysis"

    def test_bs03h_skill_validate_definition(self) -> None:
        """TC-BS03-h: 스킬 정의 유효성 검증이 통과됨."""
        for defn in [MARITIME_QA_SKILL, VESSEL_REPORT_SKILL, ROUTE_ANALYSIS_SKILL]:
            errors = defn.validate()
            assert errors == [], f"{defn.name} validation errors: {errors}"
