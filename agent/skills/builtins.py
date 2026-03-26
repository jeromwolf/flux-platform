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
# LLM provider singleton (lazy-loaded)
# ---------------------------------------------------------------------------

_llm_provider: Any = None


def _get_llm_provider() -> Any | None:
    """Get or create the LLM provider singleton for skills.

    Returns:
        A real LLM provider instance, or None if only a StubLLMProvider is
        available or if initialisation fails entirely.
    """
    global _llm_provider
    if _llm_provider is not None:
        return _llm_provider
    try:
        from agent.llm.providers import create_llm_provider  # noqa: PLC0415

        _llm_provider = create_llm_provider()
        # Treat StubLLMProvider as "no real LLM" so skills fall back to templates.
        if _llm_provider.__class__.__name__ == "StubLLMProvider":
            logger.debug("Only StubLLMProvider available, LLM synthesis disabled")
            return None
        logger.info("LLM provider for skills: %s", type(_llm_provider).__name__)
        return _llm_provider
    except Exception as exc:  # pragma: no cover
        logger.debug("LLM provider unavailable: %s", exc)
        return None


def reset_llm_provider() -> None:
    """Reset the LLM provider singleton (intended for testing)."""
    global _llm_provider
    _llm_provider = None

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
    """문서 및 KG 데이터를 기반으로 답변을 합성한다.

    실제 LLM 프로바이더가 사용 가능하면 LLM을 호출하여 답변을 생성하고,
    그렇지 않으면 템플릿 기반 답변을 반환한다.

    Args:
        question: 원본 질문.
        doc_data: 문서 검색 결과.
        kg_data: KG 질의 결과.
        language: 응답 언어.

    Returns:
        JSON 직렬화된 답변 딕셔너리 문자열.
        항상 ``question`` 키와 ``language`` 키를 포함한다.
    """
    doc_count = len(doc_data.get("documents", []))
    kg_results = len(kg_data.get("results", []))
    is_stub = doc_data.get("stub", False) or kg_data.get("stub", False)

    llm = _get_llm_provider()

    if llm is None:
        # Template fallback — preserves existing JSON contract
        answer: dict[str, Any] = {
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

    # Build context from data sources
    context_parts: list[str] = []

    docs = doc_data.get("documents", [])
    if docs:
        doc_texts = []
        for d in docs[:5]:  # top 5 documents only
            title = d.get("title", d.get("filename", "문서"))
            snippet = d.get("snippet", d.get("content", ""))[:500]
            doc_texts.append(f"- [{title}]: {snippet}")
        context_parts.append("## 문서 검색 결과\n" + "\n".join(doc_texts))

    kg_items = kg_data.get("results", [])
    if kg_items:
        kg_texts = [f"- {r}" for r in kg_items[:10]]  # top 10 KG results
        context_parts.append("## 지식그래프 데이터\n" + "\n".join(kg_texts))

    context = "\n\n".join(context_parts) if context_parts else "(검색 결과 없음)"

    system_prompt = (
        "당신은 해사 도메인 전문 AI 어시스턴트입니다. "
        "주어진 문서와 지식그래프 데이터를 기반으로 정확하고 간결한 한국어 답변을 생성하세요. "
        "답변에는 출처를 포함하고, 확인되지 않은 정보는 추측하지 마세요."
    )
    prompt = (
        f"## 질문\n{question}\n\n"
        f"## 참고 자료\n{context}\n\n"
        "위 자료를 기반으로 질문에 답변해주세요."
    )

    try:
        llm_answer = llm.generate(
            prompt=prompt,
            system=system_prompt,
            temperature=0.3,
            max_tokens=1024,
        )
        answer = {
            "question": question,
            "language": language,
            "document_sources": doc_count,
            "kg_results": kg_results,
            "answer": llm_answer,
            "stub": False,
        }
    except Exception as exc:  # pragma: no cover
        logger.warning("LLM synthesis failed: %s", exc)
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

    실제 LLM 프로바이더가 사용 가능하면 LLM으로 서술형 분석을 추가하고,
    그렇지 않으면 구조화된 JSON 보고서를 반환한다.

    Args:
        vessel_query: 검색어.
        vessel_data: 선박 검색 결과.
        kg_data: KG 관계 데이터.

    Returns:
        JSON 직렬화된 보고서 문자열.
        항상 ``report_type``, ``vessel_count``, ``vessels`` 키를 포함한다.
    """
    vessels = vessel_data.get("vessels", [])
    kg_results = kg_data.get("results", [])

    # Base report skeleton — always present in output regardless of LLM availability
    base_report: dict[str, Any] = {
        "report_type": "vessel_status",
        "query": vessel_query,
        "vessel_count": len(vessels),
        "vessels": vessels,
        "kg_summary": {
            "cypher": kg_data.get("cypher", ""),
            "results": kg_results,
        },
        "stub": vessel_data.get("stub", False),
    }

    llm = _get_llm_provider()
    if llm is None:
        return json.dumps(base_report, ensure_ascii=False)

    vessel_info = json.dumps(vessels[:5], ensure_ascii=False, indent=2) if vessels else "(선박 데이터 없음)"
    kg_info = json.dumps(kg_results[:10], ensure_ascii=False, indent=2) if kg_results else "(KG 데이터 없음)"

    system_prompt = (
        "당신은 해사 분석 전문가입니다. "
        "선박 데이터와 지식그래프 정보를 기반으로 간결한 분석 의견을 한국어로 제공하세요."
    )
    prompt = (
        f"## 선박 검색어\n{vessel_query}\n\n"
        f"## 선박 데이터\n{vessel_info}\n\n"
        f"## 지식그래프 컨텍스트\n{kg_info}\n\n"
        "위 데이터를 기반으로 선박 현황과 주요 특이사항을 간결하게 분석해주세요."
    )

    try:
        analysis = llm.generate(prompt=prompt, system=system_prompt, temperature=0.3, max_tokens=1024)
        base_report["analysis"] = analysis
        base_report["stub"] = False
    except Exception as exc:  # pragma: no cover
        logger.warning("LLM vessel report failed: %s", exc)
        # Keep base_report as-is; stub flag reflects original data

    return json.dumps(base_report, ensure_ascii=False)


def _format_route_analysis(
    origin: str,
    destination: str,
    route_data: dict[str, Any],
) -> str:
    """항로 분석 보고서를 JSON 형태로 포맷한다.

    NOTE: Weather/risk API integration is a separate work item.
    Currently returns stub risk data. Keeping as-is until external APIs are
    available (planned for Y2).

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
