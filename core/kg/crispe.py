"""CRISPE 프롬프트 프레임워크 — LLM 기반 Cypher 쿼리 생성.

CRISPE는 LLM 프롬프트를 구조적으로 구성하는 프레임워크입니다:
- Capacity   : AI의 도메인 전문성 정의
- Role       : 작업에 대한 구체적인 역할
- Insight    : 스키마 컨텍스트 (노드 레이블, 관계 타입, 속성)
- Statement  : 사용자의 자연어 쿼리
- Personality: 출력 형식 제약 조건
- Experiment : 반복/개선 힌트

Usage::

    from kg.crispe import CRISPEPromptBuilder, SchemaContext, get_default_maritime_schema

    builder = CRISPEPromptBuilder()
    schema = get_default_maritime_schema()
    prompt = builder.build_prompt("Find all container ships near Busan port", schema)

    # LLM 기반 생성 (LLMProvider 프로토콜 구현체 필요)
    from agent.llm.providers import create_llm_provider
    from kg.crispe import LLMCypherGenerator

    llm = create_llm_provider("auto")
    generator = LLMCypherGenerator(llm_provider=llm)
    result = generator.generate("부산항 근처 컨테이너선 목록", schema)
    print(result.query)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from kg.query_generator import GeneratedQuery

logger = logging.getLogger(__name__)


# =============================================================================
# 설정 데이터클래스
# =============================================================================


@dataclass(frozen=True)
class CRISPEConfig:
    """CRISPE 프롬프트 생성 설정.

    Attributes:
        capacity: AI 전문성 설명 (예: 해사 KG 전문가).
        role: 작업에 대한 구체적인 역할 (예: Cypher 쿼리 번역가).
        personality: 출력 형식 제약 조건 (예: 설명 없이 유효한 Cypher만 반환).
        experiment: 반복/개선 힌트 (예: 모호한 쿼리에 대한 가장 일반적인 해석 사용).
        domain: 도메인 이름 (예: maritime).
    """

    capacity: str = (
        "You are an expert in Neo4j Cypher query language with deep knowledge of "
        "maritime knowledge graphs, including vessel tracking, port operations, "
        "voyage management, and maritime safety domains."
    )
    role: str = "Cypher query translator"
    personality: str = (
        "Return ONLY valid Cypher. No explanation. No markdown. "
        "No additional text before or after the query."
    )
    experiment: str = (
        "Prefer the most common interpretation for ambiguous queries. "
        "Use MATCH/RETURN patterns. Avoid OPTIONAL MATCH unless explicitly needed. "
        "Always use node aliases (e.g. v for Vessel, p for Port)."
    )
    domain: str = "maritime"


# =============================================================================
# 스키마 컨텍스트
# =============================================================================


@dataclass(frozen=True)
class SchemaContext:
    """KG 스키마 정보 — CRISPE 프롬프트의 Insight 섹션에 사용됩니다.

    Attributes:
        node_labels: 사용 가능한 노드 레이블 목록 (예: ["Vessel", "Port", "Route"]).
        relationship_types: 사용 가능한 관계 타입 목록 (예: ["DOCKED_AT", "OPERATES_ON"]).
        properties: 레이블 → 속성명 목록 매핑 (예: {"Vessel": ["name", "mmsi"]}).
        sample_queries: 퓨샷 학습을 위한 (자연어, Cypher) 예제 쌍 목록.
    """

    node_labels: tuple[str, ...]
    relationship_types: tuple[str, ...]
    properties: dict[str, list[str]]
    sample_queries: tuple[tuple[str, str], ...]

    def __init__(
        self,
        node_labels: list[str],
        relationship_types: list[str],
        properties: dict[str, list[str]],
        sample_queries: list[tuple[str, str]],
    ) -> None:
        # frozen dataclass에서 mutable 초기화를 위해 object.__setattr__ 사용
        object.__setattr__(self, "node_labels", tuple(node_labels))
        object.__setattr__(self, "relationship_types", tuple(relationship_types))
        object.__setattr__(self, "properties", dict(properties))
        object.__setattr__(self, "sample_queries", tuple(tuple(p) for p in sample_queries))


# =============================================================================
# CRISPE 프롬프트 빌더
# =============================================================================


class CRISPEPromptBuilder:
    """CRISPE 프레임워크 기반 LLM 프롬프트 빌더.

    Capacity, Role, Insight, Statement, Personality, Experiment의
    6개 섹션으로 구조화된 프롬프트를 생성합니다.

    Args:
        config: 선택적 CRISPEConfig 인스턴스. 없으면 기본 설정 사용.

    Example::

        builder = CRISPEPromptBuilder()
        schema = get_default_maritime_schema()
        prompt = builder.build_prompt("Find vessels near Busan", schema)
    """

    def __init__(self, config: CRISPEConfig | None = None) -> None:
        self._config = config or CRISPEConfig()

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------

    def build_prompt(self, query: str, schema: SchemaContext) -> str:
        """전체 CRISPE 프롬프트를 생성합니다.

        Args:
            query: 번역할 자연어 쿼리.
            schema: KG 스키마 컨텍스트 (노드, 관계, 속성, 예제 포함).

        Returns:
            구조화된 CRISPE 프롬프트 문자열.
        """
        sections = [
            self._build_capacity_section(),
            self._build_role_section(),
            self._build_insight_section(schema),
            self._build_statement_section(query),
            self._build_personality_section(),
            self._build_experiment_section(),
        ]
        return "\n\n".join(sections)

    def build_prompt_with_history(
        self,
        query: str,
        schema: SchemaContext,
        history: list[tuple[str, str]],
    ) -> str:
        """대화 히스토리를 포함한 CRISPE 프롬프트를 생성합니다.

        반복적 개선(refinement) 시나리오에서 이전 질문/응답 컨텍스트를
        포함하여 더 정확한 Cypher 생성을 유도합니다.

        Args:
            query: 현재 자연어 쿼리.
            schema: KG 스키마 컨텍스트.
            history: (자연어 질문, 생성된 Cypher) 쌍으로 이루어진 이전 대화 목록.
                가장 오래된 항목부터 최신 순으로 정렬.

        Returns:
            히스토리 섹션이 포함된 구조화된 CRISPE 프롬프트 문자열.
        """
        sections = [
            self._build_capacity_section(),
            self._build_role_section(),
            self._build_insight_section(schema),
        ]

        # 히스토리 섹션 추가 (있는 경우)
        if history:
            sections.append(self._build_history_section(history))

        sections.extend([
            self._build_statement_section(query),
            self._build_personality_section(),
            self._build_experiment_section(),
        ])

        return "\n\n".join(sections)

    # ------------------------------------------------------------------
    # 섹션 빌더 (내부)
    # ------------------------------------------------------------------

    def _build_capacity_section(self) -> str:
        """[Capacity] 섹션을 생성합니다."""
        return f"[Capacity]\n{self._config.capacity}"

    def _build_role_section(self) -> str:
        """[Role] 섹션을 생성합니다."""
        return (
            f"[Role]\n"
            f"Your task is to translate natural language questions into precise "
            f"Cypher queries for a {self._config.domain} knowledge graph. "
            f"You are acting as a {self._config.role}."
        )

    def _build_insight_section(self, schema: SchemaContext) -> str:
        """[Insight] 섹션을 생성합니다 — 스키마 + 퓨샷 예제 포함."""
        lines = ["[Insight]", "The knowledge graph has the following schema:", ""]

        # 노드 레이블
        labels_str = ", ".join(schema.node_labels)
        lines.append(f"Node Labels: {labels_str}")

        # 관계 타입
        rels_str = ", ".join(schema.relationship_types)
        lines.append(f"Relationship Types: {rels_str}")

        # 속성 (레이블별)
        if schema.properties:
            lines.append("Properties:")
            for label, props in schema.properties.items():
                props_str = ", ".join(props)
                lines.append(f"  - {label}: {props_str}")

        # 퓨샷 예제
        if schema.sample_queries:
            lines.append("")
            lines.append("Example queries:")
            for nl_query, cypher_query in schema.sample_queries:
                lines.append(f"Q: {nl_query}")
                lines.append(f"A: {cypher_query}")
                lines.append("")  # 가독성을 위한 빈 줄

        return "\n".join(lines).rstrip()

    def _build_statement_section(self, query: str) -> str:
        """[Statement] 섹션을 생성합니다."""
        return (
            f"[Statement]\n"
            f"Translate the following question into a Cypher query:\n"
            f"{query}"
        )

    def _build_personality_section(self) -> str:
        """[Personality] 섹션을 생성합니다."""
        return f"[Personality]\n{self._config.personality}"

    def _build_experiment_section(self) -> str:
        """[Experiment] 섹션을 생성합니다."""
        return f"[Experiment]\n{self._config.experiment}"

    def _build_history_section(self, history: list[tuple[str, str]]) -> str:
        """[History] 섹션을 생성합니다 — 이전 대화 컨텍스트 포함."""
        lines = ["[History]", "Previous conversation context:"]
        for i, (prev_query, prev_cypher) in enumerate(history, start=1):
            lines.append(f"Turn {i}:")
            lines.append(f"  Q: {prev_query}")
            lines.append(f"  A: {prev_cypher}")
        return "\n".join(lines)


# =============================================================================
# Cypher 추출 헬퍼
# =============================================================================


def _extract_cypher(text: str) -> str:
    """LLM 응답 텍스트에서 Cypher 쿼리만 추출합니다.

    다음 형식을 처리합니다:
    1. 순수 Cypher (MATCH/RETURN으로 시작하는 텍스트)
    2. ```cypher ... ``` 마크다운 코드 펜스
    3. ``` ... ``` 일반 코드 펜스
    4. "MATCH "로 시작하는 접두사 라인

    Args:
        text: LLM이 생성한 원시 텍스트.

    Returns:
        추출된 Cypher 쿼리 문자열 (앞뒤 공백 제거).
        Cypher를 찾지 못한 경우 원본 텍스트 반환.
    """
    stripped = text.strip()

    # 1. ```cypher ... ``` 마크다운 코드 펜스 처리
    cypher_fence = re.search(
        r"```cypher\s*\n(.*?)```",
        stripped,
        re.DOTALL | re.IGNORECASE,
    )
    if cypher_fence:
        return cypher_fence.group(1).strip()

    # 2. 일반 ``` ... ``` 코드 펜스 처리
    generic_fence = re.search(
        r"```\s*\n(.*?)```",
        stripped,
        re.DOTALL,
    )
    if generic_fence:
        candidate = generic_fence.group(1).strip()
        # Cypher 키워드로 시작하는 경우만 추출
        if _looks_like_cypher(candidate):
            return candidate

    # 3. MATCH/RETURN/CREATE/MERGE 등 Cypher 키워드 라인 탐색
    # 멀티라인 Cypher 블록을 감지: 첫 번째 Cypher 키워드 라인부터 끝까지
    cypher_start = re.search(
        r"^(MATCH|RETURN|CREATE|MERGE|DELETE|DETACH|WITH|CALL|OPTIONAL|UNWIND|WHERE)",
        stripped,
        re.IGNORECASE | re.MULTILINE,
    )
    if cypher_start:
        # 해당 위치부터 텍스트 끝까지 추출 (후속 설명 텍스트는 제거)
        cypher_text = stripped[cypher_start.start():].strip()
        # 빈 줄 이후에 설명 텍스트가 있다면 제거
        first_blank = re.search(r"\n\s*\n", cypher_text)
        if first_blank:
            candidate = cypher_text[:first_blank.start()].strip()
            if _looks_like_cypher(candidate):
                return candidate
        return cypher_text

    # 4. 추출 실패 시 원본 텍스트 반환 (로그 경고)
    logger.warning(
        "Cypher extraction failed — no recognisable pattern found. "
        "Returning raw text (%d chars).",
        len(stripped),
    )
    return stripped


def _looks_like_cypher(text: str) -> bool:
    """텍스트가 Cypher 쿼리처럼 보이는지 간단히 확인합니다."""
    cypher_keywords = re.compile(
        r"\b(MATCH|RETURN|CREATE|MERGE|DELETE|DETACH|WITH|CALL|OPTIONAL|UNWIND|WHERE)\b",
        re.IGNORECASE,
    )
    return bool(cypher_keywords.search(text))


# =============================================================================
# LLM Cypher 생성기
# =============================================================================


class LLMCypherGenerator:
    """CRISPE 프롬프트 + LLM을 사용하여 자연어를 Cypher 쿼리로 변환합니다.

    LLM 프로바이더는 ``agent.llm.providers.LLMProvider`` 프로토콜을
    따라야 합니다 (``generate(prompt, system, temperature, max_tokens) -> str``).

    Args:
        llm_provider: LLMProvider 프로토콜을 구현한 인스턴스.
            (OllamaLLMProvider, OpenAILLMProvider, AnthropicLLMProvider 등)
        config: 선택적 CRISPEConfig. 없으면 기본 해사 도메인 설정 사용.

    Example::

        from agent.llm.providers import create_llm_provider
        from kg.crispe import LLMCypherGenerator, get_default_maritime_schema

        llm = create_llm_provider("auto")
        generator = LLMCypherGenerator(llm_provider=llm)
        schema = get_default_maritime_schema()

        result = generator.generate("부산항에 정박 중인 컨테이너선 목록", schema)
        print(result.query)
    """

    def __init__(
        self,
        llm_provider: Any,  # LLMProvider 프로토콜을 따르는 임의 객체
        config: CRISPEConfig | None = None,
    ) -> None:
        # NOTE: llm_provider는 agent.llm.providers.LLMProvider 프로토콜을
        # 구현해야 합니다. Any 타입으로 선언하여 직접 의존성을 피합니다.
        self._llm = llm_provider
        self._builder = CRISPEPromptBuilder(config)

    def generate(self, query: str, schema: SchemaContext) -> GeneratedQuery:
        """자연어 쿼리를 CRISPE 프롬프트와 LLM을 사용해 Cypher로 변환합니다.

        Args:
            query: 번역할 자연어 쿼리 (한국어 또는 영어).
            schema: KG 스키마 컨텍스트 (노드, 관계, 속성, 예제 포함).

        Returns:
            생성된 Cypher 쿼리를 담은 GeneratedQuery 인스턴스.
            language 필드는 항상 "cypher"입니다.

        Raises:
            Exception: LLM 호출 실패 시 원래 예외를 re-raise합니다.
        """
        # 1. CRISPE 프롬프트 생성
        prompt = self._builder.build_prompt(query, schema)
        logger.debug("CRISPE prompt built (%d chars) for query: %s", len(prompt), query)

        # 2. LLM 호출 — LLMProvider.generate() -> LLMResponse
        llm_response = self._llm.generate(prompt)
        raw_response = llm_response.text if hasattr(llm_response, "text") else str(llm_response)
        logger.debug("LLM raw response (%d chars)", len(raw_response))

        # 3. Cypher 추출
        cypher = _extract_cypher(raw_response)
        logger.debug("Extracted Cypher: %s", cypher[:200] if cypher else "(empty)")

        # 4. GeneratedQuery 반환
        return GeneratedQuery(
            language="cypher",
            query=cypher,
            parameters={},
            explanation=f"LLM-generated Cypher via CRISPE for: {query}",
            estimated_complexity="moderate",
        )

    def generate_with_history(
        self,
        query: str,
        schema: SchemaContext,
        history: list[tuple[str, str]],
    ) -> GeneratedQuery:
        """대화 히스토리를 포함하여 Cypher를 생성합니다.

        반복적 개선 시나리오에서 이전 질문/Cypher 쌍을 컨텍스트로
        제공하여 더 정확한 Cypher 생성을 유도합니다.

        Args:
            query: 현재 자연어 쿼리.
            schema: KG 스키마 컨텍스트.
            history: (자연어 질문, 생성된 Cypher) 쌍으로 이루어진 이전 대화 목록.

        Returns:
            생성된 Cypher 쿼리를 담은 GeneratedQuery 인스턴스.
        """
        prompt = self._builder.build_prompt_with_history(query, schema, history)
        logger.debug(
            "CRISPE prompt with history built (%d chars) for query: %s",
            len(prompt),
            query,
        )

        llm_response = self._llm.generate(prompt)
        raw_response = llm_response.text if hasattr(llm_response, "text") else str(llm_response)

        cypher = _extract_cypher(raw_response)

        return GeneratedQuery(
            language="cypher",
            query=cypher,
            parameters={},
            explanation=f"LLM-generated Cypher via CRISPE (with history) for: {query}",
            estimated_complexity="moderate",
        )


# =============================================================================
# 기본 해사 도메인 스키마
# =============================================================================


def get_default_maritime_schema() -> SchemaContext:
    """해사 도메인용 기본 KG 스키마를 반환합니다.

    퓨샷 학습을 위한 3개의 예제 쿼리 쌍을 포함합니다.

    Returns:
        해사 도메인 노드, 관계, 속성, 예제 쌍이 채워진 SchemaContext 인스턴스.
    """
    node_labels = [
        "Vessel",       # 선박
        "Port",         # 항구
        "Route",        # 항로
        "Voyage",       # 항해
        "Company",      # 선사/회사
        "VTSArea",      # 선박교통서비스 구역
        "Cargo",        # 화물
        "Crew",         # 선원
        "Flag",         # 선박 국적 (기국)
        "AnchorageArea", # 정박지
    ]

    relationship_types = [
        "DOCKED_AT",        # 선박 → 항구 (정박)
        "DEPARTS_FROM",     # 항해 → 항구 (출항)
        "ARRIVES_AT",       # 항해 → 항구 (입항)
        "OPERATES_ON",      # 선박 → 항로 (운항)
        "OWNED_BY",         # 선박 → 회사 (소유)
        "OPERATED_BY",      # 선박 → 회사 (운항사)
        "LOCATED_IN",       # 항구 → VTSArea (위치)
        "CARRIES",          # 항해 → 화물 (화물 적재)
        "CREWED_BY",        # 선박 → 선원 (승선)
        "REGISTERED_UNDER", # 선박 → 기국 (등록)
        "ANCHORED_AT",      # 선박 → 정박지 (정박 대기)
        "HAS_VOYAGE",       # 선박 → 항해 (항해 기록)
        "CONNECTS",         # 항로 → 항구 (항구 연결)
    ]

    properties: dict[str, list[str]] = {
        "Vessel": [
            "name",         # 선박명
            "vesselType",   # 선박 유형 (ContainerShip, Tanker, BulkCarrier 등)
            "callSign",     # 호출 부호
            "mmsi",         # MMSI 번호 (9자리)
            "imo",          # IMO 번호
            "tonnage",      # 총톤수
            "length",       # 선박 길이 (m)
            "beam",         # 선박 폭 (m)
            "draft",        # 흘수 (m)
            "flag",         # 기국 코드 (ISO 3166-1 alpha-2)
            "buildYear",    # 건조 연도
            "status",       # 현재 상태 (UNDERWAY, ANCHORED, MOORED 등)
        ],
        "Port": [
            "name",         # 항구명
            "unlocode",     # UN/LOCODE (예: KRPUS for 부산)
            "country",      # 국가 코드
            "latitude",     # 위도
            "longitude",    # 경도
            "portType",     # 항구 유형 (COMMERCIAL, FISHING, NAVAL 등)
            "maxDraft",     # 최대 허용 흘수 (m)
        ],
        "Route": [
            "name",         # 항로명
            "routeType",    # 항로 유형 (INTERNATIONAL, COASTAL, INLAND)
            "distance",     # 거리 (해리)
            "waypoints",    # 경유지 목록 (JSON)
        ],
        "Voyage": [
            "voyageId",     # 항해 식별자
            "departureTime", # 출항 시각 (ISO 8601)
            "arrivalTime",  # 입항 시각 (ISO 8601)
            "status",       # 항해 상태 (PLANNED, UNDERWAY, COMPLETED)
            "cargoType",    # 화물 유형
        ],
        "Company": [
            "name",         # 회사명
            "country",      # 등록 국가
            "imoCompanyId", # IMO 회사 식별자
        ],
        "VTSArea": [
            "name",         # VTS 구역명
            "areaCode",     # 구역 코드
            "country",      # 관할 국가
        ],
    }

    # 퓨샷 학습 예제 (자연어 → Cypher 쌍)
    sample_queries: list[tuple[str, str]] = [
        (
            "Find all container ships currently docked at Busan port",
            (
                "MATCH (v:Vessel)-[:DOCKED_AT]->(p:Port) "
                "WHERE v.vesselType = 'ContainerShip' AND p.name = 'Busan' "
                "RETURN v.name, v.mmsi, v.callSign"
            ),
        ),
        (
            "List all voyages departing from Incheon port in the last month",
            (
                "MATCH (voy:Voyage)-[:DEPARTS_FROM]->(p:Port) "
                "WHERE p.name = 'Incheon' "
                "AND voy.departureTime >= datetime() - duration('P30D') "
                "RETURN voy.voyageId, voy.departureTime, voy.status "
                "ORDER BY voy.departureTime DESC"
            ),
        ),
        (
            "Find the company that owns the vessel with MMSI 440123456",
            (
                "MATCH (v:Vessel)-[:OWNED_BY]->(c:Company) "
                "WHERE v.mmsi = '440123456' "
                "RETURN c.name, c.country, c.imoCompanyId"
            ),
        ),
        (
            "Count the number of vessels by type currently anchored",
            (
                "MATCH (v:Vessel) "
                "WHERE v.status = 'ANCHORED' "
                "RETURN v.vesselType AS vesselType, count(v) AS count "
                "ORDER BY count DESC"
            ),
        ),
    ]

    return SchemaContext(
        node_labels=node_labels,
        relationship_types=relationship_types,
        properties=properties,
        sample_queries=sample_queries,
    )
