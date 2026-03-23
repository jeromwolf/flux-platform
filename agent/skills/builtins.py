"""Built-in agent skills for the IMSP platform."""
from __future__ import annotations

import json
import logging
from typing import Any

from agent.skills.models import SkillDefinition, SkillResult
from agent.skills.registry import SkillRegistry
from agent.tools.builtins import create_builtin_registry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Skill definitions (frozen dataclasses)
# ---------------------------------------------------------------------------

MARITIME_QA_SKILL = SkillDefinition(
    name="maritime_qa",
    description=(
        "해사 질문에 대해 KG와 문서 검색을 결합하여 답변을 생성한다. "
        "document_search → kg_query → 답변 합성 순서로 실행."
    ),
    category="maritime",
    required_tools=("document_search", "kg_query"),
    parameters={
        "question": {
            "type": "string",
            "description": "해사 관련 질문",
        },
        "language": {
            "type": "string",
            "description": "응답 언어 (ko, en). 기본값: ko",
        },
    },
)

VESSEL_REPORT_SKILL = SkillDefinition(
    name="vessel_report",
    description=(
        "선박 현황 보고서를 생성한다. "
        "vessel_search → kg_query(관계 조회) → 보고서 포맷 순서로 실행."
    ),
    category="maritime",
    required_tools=("vessel_search", "kg_query"),
    parameters={
        "vessel_query": {
            "type": "string",
            "description": "선박 검색어 (이름, MMSI, IMO)",
        },
    },
)

ROUTE_ANALYSIS_SKILL = SkillDefinition(
    name="route_analysis",
    description=(
        "해상 항로 분석 보고서를 생성한다. "
        "route_query → 위험도/날씨 데이터 → 분석 보고서 순서로 실행."
    ),
    category="maritime",
    required_tools=("route_query",),
    parameters={
        "origin": {
            "type": "string",
            "description": "출발 항구 이름",
        },
        "destination": {
            "type": "string",
            "description": "도착 항구 이름",
        },
    },
)

# ---------------------------------------------------------------------------
# Skill handler functions
# ---------------------------------------------------------------------------

# 스킬 내에서 도구를 직접 호출하기 위한 내부 레지스트리
_tool_registry = create_builtin_registry()


def _handle_maritime_qa(
    question: str,
    language: str = "ko",
) -> SkillResult:
    """해사 Q&A 스킬 핸들러.

    document_search로 관련 문서를 찾고 kg_query로 KG에서 데이터를 조회하여
    답변을 합성한다.

    Args:
        question: 해사 관련 질문.
        language: 응답 언어 코드.

    Returns:
        SkillResult 인스턴스.
    """
    steps_taken = 0

    # Step 1: 문서 검색
    doc_result = _tool_registry.execute("document_search", {"query": question, "top_k": 3})
    steps_taken += 1
    if not doc_result.success:
        return SkillResult(
            skill_name="maritime_qa",
            output="",
            success=False,
            error=f"문서 검색 실패: {doc_result.error}",
            steps_taken=steps_taken,
        )

    # Step 2: KG 질의
    kg_result = _tool_registry.execute("kg_query", {"query": question, "language": language})
    steps_taken += 1
    if not kg_result.success:
        return SkillResult(
            skill_name="maritime_qa",
            output="",
            success=False,
            error=f"KG 질의 실패: {kg_result.error}",
            steps_taken=steps_taken,
        )

    # Step 3: 답변 합성 (Y2에서 LLM 호출로 교체 예정)
    try:
        doc_data: dict[str, Any] = json.loads(doc_result.output)
        kg_data: dict[str, Any] = json.loads(kg_result.output)
    except json.JSONDecodeError:
        doc_data = {}
        kg_data = {}

    steps_taken += 1
    answer = _synthesize_answer(question, doc_data, kg_data, language)

    return SkillResult(
        skill_name="maritime_qa",
        output=answer,
        success=True,
        steps_taken=steps_taken,
    )


def _handle_vessel_report(vessel_query: str) -> SkillResult:
    """선박 현황 보고서 스킬 핸들러.

    Args:
        vessel_query: 선박 검색어.

    Returns:
        SkillResult 인스턴스.
    """
    steps_taken = 0

    # Step 1: 선박 검색
    search_result = _tool_registry.execute("vessel_search", {"query": vessel_query})
    steps_taken += 1
    if not search_result.success:
        return SkillResult(
            skill_name="vessel_report",
            output="",
            success=False,
            error=f"선박 검색 실패: {search_result.error}",
            steps_taken=steps_taken,
        )

    # Step 2: KG에서 선박 관계 정보 조회
    kg_query = f"선박 {vessel_query} 관련 항로, 화물, 기항지 정보"
    kg_result = _tool_registry.execute("kg_query", {"query": kg_query})
    steps_taken += 1

    # Step 3: 보고서 포맷
    try:
        vessel_data: dict[str, Any] = json.loads(search_result.output)
        kg_data: dict[str, Any] = json.loads(kg_result.output) if kg_result.success else {}
    except json.JSONDecodeError:
        vessel_data = {}
        kg_data = {}

    steps_taken += 1
    report = _format_vessel_report(vessel_query, vessel_data, kg_data)

    return SkillResult(
        skill_name="vessel_report",
        output=report,
        success=True,
        steps_taken=steps_taken,
    )


def _handle_route_analysis(origin: str, destination: str) -> SkillResult:
    """해상 항로 분석 스킬 핸들러.

    Args:
        origin: 출발 항구.
        destination: 도착 항구.

    Returns:
        SkillResult 인스턴스.
    """
    steps_taken = 0

    # Step 1: 항로 조회
    route_result = _tool_registry.execute(
        "route_query",
        {"origin": origin, "destination": destination},
    )
    steps_taken += 1
    if not route_result.success:
        return SkillResult(
            skill_name="route_analysis",
            output="",
            success=False,
            error=f"항로 조회 실패: {route_result.error}",
            steps_taken=steps_taken,
        )

    # Step 2: 위험도/기상 데이터 (stub — Y2에서 실제 데이터로 교체)
    steps_taken += 1
    try:
        route_data: dict[str, Any] = json.loads(route_result.output)
    except json.JSONDecodeError:
        route_data = {}

    # Step 3: 분석 보고서 생성
    steps_taken += 1
    report = _format_route_analysis(origin, destination, route_data)

    return SkillResult(
        skill_name="route_analysis",
        output=report,
        success=True,
        steps_taken=steps_taken,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _synthesize_answer(
    question: str,
    doc_data: dict[str, Any],
    kg_data: dict[str, Any],
    language: str,
) -> str:
    """문서 및 KG 데이터를 기반으로 답변을 합성한다 (stub).

    Args:
        question: 원본 질문.
        doc_data: 문서 검색 결과.
        kg_data: KG 질의 결과.
        language: 응답 언어.

    Returns:
        합성된 답변 문자열.
    """
    doc_count = len(doc_data.get("documents", []))
    kg_results = len(kg_data.get("results", []))
    is_stub = doc_data.get("stub", False) or kg_data.get("stub", False)

    answer = {
        "question": question,
        "language": language,
        "document_sources": doc_count,
        "kg_results": kg_results,
        "answer": (
            f"질문 '{question}'에 대한 답변: "
            f"문서 {doc_count}건, KG 데이터 {kg_results}건을 참고했습니다."
        ),
        "stub": is_stub,
    }
    return json.dumps(answer, ensure_ascii=False)


def _format_vessel_report(
    vessel_query: str,
    vessel_data: dict[str, Any],
    kg_data: dict[str, Any],
) -> str:
    """선박 보고서를 JSON 형태로 포맷한다.

    Args:
        vessel_query: 검색어.
        vessel_data: 선박 검색 결과.
        kg_data: KG 관계 데이터.

    Returns:
        JSON 직렬화된 보고서 문자열.
    """
    vessels = vessel_data.get("vessels", [])
    report = {
        "report_type": "vessel_status",
        "query": vessel_query,
        "vessel_count": len(vessels),
        "vessels": vessels,
        "kg_summary": {
            "cypher": kg_data.get("cypher", ""),
            "results": kg_data.get("results", []),
        },
        "stub": vessel_data.get("stub", False),
    }
    return json.dumps(report, ensure_ascii=False)


def _format_route_analysis(
    origin: str,
    destination: str,
    route_data: dict[str, Any],
) -> str:
    """항로 분석 보고서를 JSON 형태로 포맷한다.

    Args:
        origin: 출발 항구.
        destination: 도착 항구.
        route_data: 항로 조회 결과.

    Returns:
        JSON 직렬화된 분석 보고서 문자열.
    """
    routes = route_data.get("routes", [])
    report = {
        "report_type": "route_analysis",
        "origin": origin,
        "destination": destination,
        "route_count": len(routes),
        "routes": routes,
        "risk_assessment": {
            "overall_risk": "low",
            "weather_risk": "unknown",
            "piracy_risk": "unknown",
        },
        "stub": route_data.get("stub", False),
    }
    return json.dumps(report, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Registry factory
# ---------------------------------------------------------------------------


def create_builtin_skills() -> SkillRegistry:
    """IMSP 내장 스킬이 모두 등록된 SkillRegistry를 생성한다.

    Returns:
        내장 스킬이 등록된 SkillRegistry 인스턴스.

    Example::

        registry = create_builtin_skills()
        result = registry.execute("maritime_qa", {"question": "부산항 수심은?"})
    """
    registry = SkillRegistry()

    registry.register(MARITIME_QA_SKILL, _handle_maritime_qa)
    registry.register(VESSEL_REPORT_SKILL, _handle_vessel_report)
    registry.register(ROUTE_ANALYSIS_SKILL, _handle_route_analysis)

    logger.info("Built-in skill registry created with %d skills", registry.skill_count)
    return registry
