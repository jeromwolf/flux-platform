"""Built-in agent tools for the IMSP platform."""
from __future__ import annotations

import json
import logging
from typing import Any

from agent.tools.models import ToolDefinition, ToolResult
from agent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool definitions (frozen dataclasses)
# ---------------------------------------------------------------------------

KG_QUERY_TOOL = ToolDefinition(
    name="kg_query",
    description=(
        "자연어 질의를 지식 그래프(KG)에서 검색한다. "
        "TextToCypherPipeline을 통해 Cypher로 변환 후 실행."
    ),
    parameters={
        "query": {
            "type": "string",
            "description": "자연어 검색 질의",
        },
        "language": {
            "type": "string",
            "description": "질의 언어 (ko, en). 기본값: ko",
        },
    },
    required_params=("query",),
    category="kg",
)

KG_SCHEMA_TOOL = ToolDefinition(
    name="kg_schema",
    description="KG 스키마 정보를 반환한다. 노드 레이블, 관계 타입, 속성 목록 포함.",
    parameters={
        "label": {
            "type": "string",
            "description": "조회할 특정 노드 레이블 (선택사항)",
        },
    },
    required_params=(),
    category="kg",
)

CYPHER_EXECUTE_TOOL = ToolDefinition(
    name="cypher_execute",
    description=(
        "원시 Cypher 쿼리를 Neo4j에서 직접 실행한다. "
        "위험 도구 — 인증된 사용자만 사용 가능."
    ),
    parameters={
        "cypher": {
            "type": "string",
            "description": "실행할 Cypher 쿼리",
        },
        "parameters": {
            "type": "object",
            "description": "쿼리 파라미터 (선택사항)",
        },
    },
    required_params=("cypher",),
    category="kg",
    is_dangerous=True,
)

VESSEL_SEARCH_TOOL = ToolDefinition(
    name="vessel_search",
    description="선박 이름, MMSI, IMO 번호로 선박을 검색한다.",
    parameters={
        "query": {
            "type": "string",
            "description": "검색어 (선박명, MMSI, IMO 번호)",
        },
        "search_type": {
            "type": "string",
            "description": "검색 유형: name | mmsi | imo (기본값: name)",
        },
    },
    required_params=("query",),
    category="maritime",
)

PORT_INFO_TOOL = ToolDefinition(
    name="port_info",
    description="항구 정보를 조회한다. 위치, 수심, 시설 등 포함.",
    parameters={
        "port_name": {
            "type": "string",
            "description": "조회할 항구 이름",
        },
    },
    required_params=("port_name",),
    category="maritime",
)

ROUTE_QUERY_TOOL = ToolDefinition(
    name="route_query",
    description="출발항과 도착항 사이의 해상 항로를 조회한다.",
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
    required_params=("origin", "destination"),
    category="maritime",
)

DOCUMENT_SEARCH_TOOL = ToolDefinition(
    name="document_search",
    description="RAG 엔진을 통해 해사 문서를 검색한다.",
    parameters={
        "query": {
            "type": "string",
            "description": "검색 질의",
        },
        "top_k": {
            "type": "integer",
            "description": "반환할 최대 결과 수 (기본값: 5)",
        },
    },
    required_params=("query",),
    category="rag",
)

# ---------------------------------------------------------------------------
# Tool handler functions (stub mode — 외부 서비스 불필요)
# ---------------------------------------------------------------------------


def _handle_kg_query(query: str, language: str = "ko") -> str:
    """KG 자연어 질의 핸들러 (stub).

    Args:
        query: 자연어 질의 문자열.
        language: 질의 언어 코드.

    Returns:
        JSON 직렬화된 쿼리 결과 문자열.
    """
    # Y2에서 core.kg.pipeline.TextToCypherPipeline으로 교체 예정
    try:
        from core.kg.pipeline import TextToCypherPipeline  # type: ignore[import]

        pipeline = TextToCypherPipeline()
        result = pipeline.run(query, language=language)
        return json.dumps(result, ensure_ascii=False, default=str)
    except ImportError:
        pass
    except Exception as exc:
        logger.warning("KG pipeline unavailable, using stub: %s", exc)

    # stub 응답
    stub_result = {
        "query": query,
        "language": language,
        "cypher": f"MATCH (n) WHERE n.name CONTAINS '{query}' RETURN n LIMIT 10",
        "results": [],
        "stub": True,
    }
    return json.dumps(stub_result, ensure_ascii=False)


def _handle_kg_schema(label: str = "") -> str:
    """KG 스키마 조회 핸들러 (stub).

    Args:
        label: 특정 노드 레이블 (없으면 전체 스키마 반환).

    Returns:
        JSON 직렬화된 스키마 문자열.
    """
    full_schema: dict[str, Any] = {
        "node_labels": [
            "Vessel", "Port", "Route", "Cargo", "Document",
            "Company", "Crew", "Incident",
        ],
        "relationship_types": [
            "DOCKED_AT", "SAILED_TO", "CARRIES", "PART_OF",
            "OWNED_BY", "CREWED_BY", "INVOLVED_IN",
        ],
        "properties": {
            "Vessel": ["mmsi", "imo", "name", "vesselType", "flag", "grossTonnage"],
            "Port": ["portId", "name", "country", "latitude", "longitude", "maxDraft"],
            "Route": ["routeId", "distance", "estimatedDays", "riskLevel"],
        },
    }

    if label:
        props = full_schema["properties"].get(label)
        if props is None:
            return json.dumps({"error": f"Unknown label: {label}"}, ensure_ascii=False)
        return json.dumps(
            {"label": label, "properties": props},
            ensure_ascii=False,
        )

    return json.dumps(full_schema, ensure_ascii=False)


def _handle_cypher_execute(
    cypher: str,
    parameters: dict[str, Any] | None = None,
) -> str:
    """Cypher 직접 실행 핸들러 (stub).

    Args:
        cypher: 실행할 Cypher 쿼리.
        parameters: 쿼리 파라미터.

    Returns:
        JSON 직렬화된 실행 결과 문자열.
    """
    parameters = parameters or {}

    # Y2에서 Neo4j 드라이버 직접 호출로 교체 예정
    stub_result = {
        "cypher": cypher,
        "parameters": parameters,
        "rows": [],
        "summary": {"counters": {}, "query_type": "r"},
        "stub": True,
    }
    return json.dumps(stub_result, ensure_ascii=False)


def _handle_vessel_search(query: str, search_type: str = "name") -> str:
    """선박 검색 핸들러 (stub).

    Args:
        query: 검색어.
        search_type: 검색 유형 (name | mmsi | imo).

    Returns:
        JSON 직렬화된 검색 결과 문자열.
    """
    # stub 데이터 — Y2에서 Neo4j 조회로 교체 예정
    if search_type not in ("name", "mmsi", "imo"):
        search_type = "name"

    stub_vessels = [
        {
            "mmsi": "440100001",
            "imo": "IMO9876543",
            "name": "BUSAN PIONEER",
            "vesselType": "container_ship",
            "flag": "KR",
            "grossTonnage": 45000,
        },
        {
            "mmsi": "440100002",
            "imo": "IMO9876544",
            "name": "KOREA SPIRIT",
            "vesselType": "bulk_carrier",
            "flag": "KR",
            "grossTonnage": 32000,
        },
    ]

    # 간단한 필터링 (실제 구현은 KG 조회)
    if search_type == "mmsi":
        vessels = [v for v in stub_vessels if v["mmsi"] == query]
    elif search_type == "imo":
        vessels = [v for v in stub_vessels if v["imo"] == query]
    else:
        vessels = [
            v for v in stub_vessels
            if query.lower() in v["name"].lower()
        ]

    result = {
        "query": query,
        "search_type": search_type,
        "count": len(vessels),
        "vessels": vessels,
        "stub": True,
    }
    return json.dumps(result, ensure_ascii=False)


def _handle_port_info(port_name: str) -> str:
    """항구 정보 조회 핸들러 (stub).

    Args:
        port_name: 조회할 항구 이름.

    Returns:
        JSON 직렬화된 항구 정보 문자열.
    """
    # stub 데이터 — Y2에서 Neo4j 조회로 교체 예정
    stub_ports: dict[str, dict[str, Any]] = {
        "부산": {
            "portId": "KRPUS",
            "name": "부산항",
            "country": "KR",
            "latitude": 35.1028,
            "longitude": 129.0403,
            "maxDraft": 16.0,
            "facilities": ["컨테이너 터미널", "벌크 터미널", "여객 터미널"],
        },
        "인천": {
            "portId": "KRINC",
            "name": "인천항",
            "country": "KR",
            "latitude": 37.4639,
            "longitude": 126.6183,
            "maxDraft": 14.0,
            "facilities": ["컨테이너 터미널", "자동차 터미널"],
        },
    }

    # 이름 매칭 (부분 일치)
    matched = None
    for key, info in stub_ports.items():
        if key in port_name or port_name in key or port_name in info["portId"]:
            matched = info
            break

    if matched is None:
        result: dict[str, Any] = {
            "port_name": port_name,
            "found": False,
            "message": f"항구를 찾을 수 없습니다: {port_name}",
            "stub": True,
        }
    else:
        result = {**matched, "stub": True}

    return json.dumps(result, ensure_ascii=False)


def _handle_route_query(origin: str, destination: str) -> str:
    """해상 항로 조회 핸들러 (stub).

    Args:
        origin: 출발 항구 이름.
        destination: 도착 항구 이름.

    Returns:
        JSON 직렬화된 항로 정보 문자열.
    """
    # stub 데이터 — Y2에서 해도 데이터/KG 조회로 교체 예정
    result = {
        "origin": origin,
        "destination": destination,
        "routes": [
            {
                "routeId": f"ROUTE_{origin[:3].upper()}_{destination[:3].upper()}_001",
                "distance": 0,  # nautical miles (stub)
                "estimatedDays": 0,
                "waypoints": [],
                "riskLevel": "low",
            }
        ],
        "stub": True,
    }
    return json.dumps(result, ensure_ascii=False)


def _handle_document_search(query: str, top_k: int = 5) -> str:
    """RAG 문서 검색 핸들러 (stub).

    Args:
        query: 검색 질의.
        top_k: 반환할 최대 결과 수.

    Returns:
        JSON 직렬화된 검색 결과 문자열.
    """
    # Y2에서 rag.engines.orchestrator.HybridRAGEngine으로 교체 예정
    try:
        from rag.engines.orchestrator import HybridRAGEngine  # type: ignore[import]

        engine = HybridRAGEngine()
        results = engine.search(query, top_k=top_k)
        return json.dumps(results, ensure_ascii=False, default=str)
    except ImportError:
        pass
    except Exception as exc:
        logger.warning("RAG engine unavailable, using stub: %s", exc)

    stub_result = {
        "query": query,
        "top_k": top_k,
        "documents": [],
        "stub": True,
    }
    return json.dumps(stub_result, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Registry factory
# ---------------------------------------------------------------------------


def create_builtin_registry() -> ToolRegistry:
    """IMSP 내장 도구가 모두 등록된 ToolRegistry를 생성한다.

    Returns:
        내장 도구가 등록된 ToolRegistry 인스턴스.

    Example::

        registry = create_builtin_registry()
        result = registry.execute("vessel_search", {"query": "BUSAN"})
    """
    registry = ToolRegistry()

    registry.register(KG_QUERY_TOOL, _handle_kg_query)
    registry.register(KG_SCHEMA_TOOL, _handle_kg_schema)
    registry.register(CYPHER_EXECUTE_TOOL, _handle_cypher_execute)
    registry.register(VESSEL_SEARCH_TOOL, _handle_vessel_search)
    registry.register(PORT_INFO_TOOL, _handle_port_info)
    registry.register(ROUTE_QUERY_TOOL, _handle_route_query)
    registry.register(DOCUMENT_SEARCH_TOOL, _handle_document_search)

    logger.info("Built-in tool registry created with %d tools", registry.tool_count)
    return registry
