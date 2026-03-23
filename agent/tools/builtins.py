"""Built-in agent tools for the IMSP platform.

Connects to real KG/RAG backends when available, falling back to
stub data when external services are unreachable.

Every handler follows the pattern:
  1. Try real backend (Neo4j, TextToCypherPipeline, HybridRAGEngine)
  2. Fall back to stub JSON data on ImportError or connection failure
  3. Never crash -- always return valid JSON string
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from agent.tools.models import ToolDefinition, ToolResult
from agent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Danger detection (mirrored from core/kg/api/routes/cypher.py)
# ---------------------------------------------------------------------------

_DANGEROUS_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bDROP\b", re.IGNORECASE),
    re.compile(
        r"\bDETACH\s+DELETE\s+(?!\s*\()?\s*\w+\s*(?!WHERE)", re.IGNORECASE
    ),
    re.compile(r"\bDELETE\b(?![\s\S]*\bWHERE\b)", re.IGNORECASE),
    re.compile(r"\bCALL\s+apoc\.schema\b", re.IGNORECASE),
    re.compile(r"\bCALL\s+apoc\.trigger\b", re.IGNORECASE),
    re.compile(r"\bCALL\s+db\.(create|drop|shutdown)\b", re.IGNORECASE),
]


def _is_dangerous(cypher: str) -> tuple[bool, str]:
    """Check whether a Cypher query contains dangerous operations.

    Args:
        cypher: The Cypher query string to check.

    Returns:
        Tuple of (is_dangerous, reason).
    """
    for pattern in _DANGEROUS_PATTERNS:
        if pattern.search(cypher):
            return True, f"Query contains a disallowed operation: {pattern.pattern}"
    return False, ""


# ---------------------------------------------------------------------------
# Neo4j helper: run a Cypher query using the sync driver
# ---------------------------------------------------------------------------


def _run_cypher(cypher: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Execute a Cypher query via the Neo4j sync driver.

    Args:
        cypher: Cypher query string.
        parameters: Optional query parameters.

    Returns:
        List of record dicts.

    Raises:
        RuntimeError: If the driver is unavailable or query fails.
    """
    from core.kg.config import get_config, get_driver

    driver = get_driver()
    cfg = get_config()
    with driver.session(database=cfg.neo4j.database) as session:
        result = session.run(cypher, parameters or {})
        rows: list[dict[str, Any]] = []
        for record in result:
            row: dict[str, Any] = {}
            for key in record.keys():
                val = record[key]
                # Serialize Neo4j Node objects
                if hasattr(val, "element_id") and hasattr(val, "labels"):
                    row[key] = {
                        "id": val.element_id,
                        "labels": list(val.labels),
                        "properties": dict(val),
                    }
                # Serialize Neo4j Relationship objects
                elif hasattr(val, "element_id") and hasattr(val, "type"):
                    row[key] = {
                        "id": val.element_id,
                        "type": val.type,
                        "properties": dict(val),
                    }
                else:
                    row[key] = val
            rows.append(row)
        return rows


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
# Tool handler functions (real backends with stub fallback)
# ---------------------------------------------------------------------------


def _handle_kg_query(query: str, language: str = "ko") -> str:
    """KG 자연어 질의 핸들러.

    Tries TextToCypherPipeline first, then falls back to direct Cypher via
    Neo4j driver, then to stub data.

    Args:
        query: 자연어 질의 문자열.
        language: 질의 언어 코드.

    Returns:
        JSON 직렬화된 쿼리 결과 문자열.
    """
    # Strategy 1: TextToCypherPipeline
    try:
        from core.kg.pipeline import TextToCypherPipeline

        pipeline = TextToCypherPipeline()
        output = pipeline.process(query)
        result: dict[str, Any] = {
            "query": query,
            "language": language,
            "success": output.success,
            "cypher": output.generated_query.query if output.generated_query else None,
            "results": [],
            "stub": False,
        }
        if output.error:
            result["error"] = output.error

        # If pipeline succeeded and produced a Cypher query, execute it
        if output.success and output.generated_query:
            try:
                rows = _run_cypher(
                    output.generated_query.query,
                    output.generated_query.parameters,
                )
                result["results"] = rows
            except Exception as exc:
                logger.warning("Cypher execution failed after pipeline: %s", exc)
                result["execution_error"] = str(exc)

        return json.dumps(result, ensure_ascii=False, default=str)
    except ImportError:
        logger.debug("TextToCypherPipeline not available, trying direct Cypher")
    except Exception as exc:
        logger.warning("KG pipeline unavailable: %s", exc)

    # Strategy 2: Direct Cypher via Neo4j driver
    try:
        cypher = f"MATCH (n) WHERE n.name CONTAINS $query RETURN n LIMIT 10"
        rows = _run_cypher(cypher, {"query": query})
        result = {
            "query": query,
            "language": language,
            "cypher": cypher,
            "results": rows,
            "stub": False,
        }
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as exc:
        logger.warning("Neo4j direct query failed, using stub: %s", exc)

    # Strategy 3: Stub fallback
    stub_result = {
        "query": query,
        "language": language,
        "cypher": f"MATCH (n) WHERE n.name CONTAINS '{query}' RETURN n LIMIT 10",
        "results": [],
        "stub": True,
    }
    return json.dumps(stub_result, ensure_ascii=False)


def _handle_kg_schema(label: str = "") -> str:
    """KG 스키마 조회 핸들러.

    Queries Neo4j for labels and relationship types, falls back to stub.

    Args:
        label: 특정 노드 레이블 (없으면 전체 스키마 반환).

    Returns:
        JSON 직렬화된 스키마 문자열.
    """
    # Try real Neo4j schema introspection
    try:
        labels_rows = _run_cypher(
            "CALL db.labels() YIELD label RETURN collect(label) AS labels"
        )
        rel_rows = _run_cypher(
            "CALL db.relationshipTypes() YIELD relationshipType "
            "RETURN collect(relationshipType) AS types"
        )

        node_labels = labels_rows[0]["labels"] if labels_rows else []
        rel_types = rel_rows[0]["types"] if rel_rows else []

        if label:
            # Query properties for a specific label
            prop_rows = _run_cypher(
                "MATCH (n:`" + label + "`) "
                "WITH keys(n) AS ks UNWIND ks AS k "
                "RETURN collect(DISTINCT k) AS properties "
                "LIMIT 1"
            )
            properties = prop_rows[0]["properties"] if prop_rows else []
            result: dict[str, Any] = {
                "label": label,
                "properties": properties,
                "stub": False,
            }
            return json.dumps(result, ensure_ascii=False)

        result = {
            "node_labels": node_labels,
            "relationship_types": rel_types,
            "stub": False,
        }
        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        logger.warning("Neo4j schema query failed, using stub: %s", exc)

    # Stub fallback
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
        "stub": True,
    }

    if label:
        props = full_schema["properties"].get(label)
        if props is None:
            return json.dumps(
                {"error": f"Unknown label: {label}", "stub": True},
                ensure_ascii=False,
            )
        return json.dumps(
            {"label": label, "properties": props, "stub": True},
            ensure_ascii=False,
        )

    return json.dumps(full_schema, ensure_ascii=False)


def _handle_cypher_execute(
    cypher: str,
    parameters: dict[str, Any] | None = None,
) -> str:
    """Cypher 직접 실행 핸들러.

    Validates for dangerous operations before execution.
    Uses Neo4j driver when available, falls back to stub.

    Args:
        cypher: 실행할 Cypher 쿼리.
        parameters: 쿼리 파라미터.

    Returns:
        JSON 직렬화된 실행 결과 문자열.
    """
    parameters = parameters or {}

    # Safety check: block dangerous operations
    dangerous, reason = _is_dangerous(cypher)
    if dangerous:
        error_result = {
            "cypher": cypher,
            "error": reason,
            "blocked": True,
        }
        return json.dumps(error_result, ensure_ascii=False)

    # Try real Neo4j execution
    try:
        rows = _run_cypher(cypher, parameters)
        result: dict[str, Any] = {
            "cypher": cypher,
            "parameters": parameters,
            "rows": rows,
            "row_count": len(rows),
            "stub": False,
        }
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as exc:
        logger.warning("Neo4j Cypher execution failed, using stub: %s", exc)

    # Stub fallback
    stub_result = {
        "cypher": cypher,
        "parameters": parameters,
        "rows": [],
        "summary": {"counters": {}, "query_type": "r"},
        "stub": True,
    }
    return json.dumps(stub_result, ensure_ascii=False)


def _handle_vessel_search(query: str, search_type: str = "name") -> str:
    """선박 검색 핸들러.

    Uses CypherBuilder to construct a parameterized query against Neo4j,
    falls back to stub data.

    Args:
        query: 검색어.
        search_type: 검색 유형 (name | mmsi | imo).

    Returns:
        JSON 직렬화된 검색 결과 문자열.
    """
    if search_type not in ("name", "mmsi", "imo"):
        search_type = "name"

    # Try real Neo4j query via CypherBuilder
    try:
        from core.kg.cypher_builder import CypherBuilder

        builder = CypherBuilder().match("(v:Vessel)")

        if search_type == "name":
            builder = builder.where(
                "v.name CONTAINS $name", {"name": query}
            )
        elif search_type == "mmsi":
            builder = builder.where(
                "v.mmsi = $mmsi", {"mmsi": query}
            )
        elif search_type == "imo":
            builder = builder.where(
                "v.imo = $imo", {"imo": query}
            )

        cypher_str, params = (
            builder
            .return_("v")
            .limit(10)
            .build()
        )

        rows = _run_cypher(cypher_str, params)

        # Extract vessel data from nodes
        vessels = []
        for row in rows:
            v = row.get("v", row)
            if isinstance(v, dict) and "properties" in v:
                vessels.append(v["properties"])
            else:
                vessels.append(v)

        result: dict[str, Any] = {
            "query": query,
            "search_type": search_type,
            "count": len(vessels),
            "vessels": vessels,
            "stub": False,
        }
        return json.dumps(result, ensure_ascii=False, default=str)
    except ImportError:
        logger.debug("CypherBuilder not available for vessel search")
    except Exception as exc:
        logger.warning("Neo4j vessel search failed, using stub: %s", exc)

    # Stub fallback
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
    """항구 정보 조회 핸들러.

    Queries Neo4j for Port nodes using CypherBuilder, falls back to stub.

    Args:
        port_name: 조회할 항구 이름.

    Returns:
        JSON 직렬화된 항구 정보 문자열.
    """
    # Try real Neo4j query
    try:
        from core.kg.cypher_builder import CypherBuilder

        cypher_str, params = (
            CypherBuilder()
            .match("(p:Port)")
            .where("p.name CONTAINS $name", {"name": port_name})
            .return_("p")
            .limit(1)
            .build()
        )

        rows = _run_cypher(cypher_str, params)
        if rows:
            p = rows[0].get("p", rows[0])
            port_data = p.get("properties", p) if isinstance(p, dict) else p
            result: dict[str, Any] = {**port_data, "stub": False}
            return json.dumps(result, ensure_ascii=False, default=str)

        # No match in Neo4j
        result = {
            "port_name": port_name,
            "found": False,
            "message": f"항구를 찾을 수 없습니다: {port_name}",
            "stub": False,
        }
        return json.dumps(result, ensure_ascii=False)
    except ImportError:
        logger.debug("CypherBuilder not available for port info")
    except Exception as exc:
        logger.warning("Neo4j port query failed, using stub: %s", exc)

    # Stub fallback
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

    matched = None
    for key, info in stub_ports.items():
        if key in port_name or port_name in key or port_name in info["portId"]:
            matched = info
            break

    if matched is None:
        result = {
            "port_name": port_name,
            "found": False,
            "message": f"항구를 찾을 수 없습니다: {port_name}",
            "stub": True,
        }
    else:
        result = {**matched, "stub": True}

    return json.dumps(result, ensure_ascii=False)


def _handle_route_query(origin: str, destination: str) -> str:
    """해상 항로 조회 핸들러.

    Queries Neo4j for route relationships between ports, falls back to stub.

    Args:
        origin: 출발 항구 이름.
        destination: 도착 항구 이름.

    Returns:
        JSON 직렬화된 항로 정보 문자열.
    """
    # Try real Neo4j query
    try:
        cypher = (
            "MATCH (o:Port)-[r:ROUTE_TO|SAILED_TO]->(d:Port) "
            "WHERE o.name CONTAINS $origin AND d.name CONTAINS $destination "
            "RETURN o, r, d LIMIT 5"
        )
        rows = _run_cypher(cypher, {"origin": origin, "destination": destination})

        if rows:
            routes = []
            for row in rows:
                route_info: dict[str, Any] = {}
                r = row.get("r", {})
                if isinstance(r, dict) and "properties" in r:
                    route_info = r["properties"]
                    route_info["type"] = r.get("type", "")
                routes.append(route_info)

            result: dict[str, Any] = {
                "origin": origin,
                "destination": destination,
                "routes": routes,
                "count": len(routes),
                "stub": False,
            }
            return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as exc:
        logger.warning("Neo4j route query failed, using stub: %s", exc)

    # Stub fallback
    result = {
        "origin": origin,
        "destination": destination,
        "routes": [
            {
                "routeId": f"ROUTE_{origin[:3].upper()}_{destination[:3].upper()}_001",
                "distance": 0,
                "estimatedDays": 0,
                "waypoints": [],
                "riskLevel": "low",
            }
        ],
        "stub": True,
    }
    return json.dumps(result, ensure_ascii=False)


def _handle_document_search(query: str, top_k: int = 5) -> str:
    """RAG 문서 검색 핸들러.

    Uses HybridRAGEngine.query() when available, falls back to stub.

    Args:
        query: 검색 질의.
        top_k: 반환할 최대 결과 수.

    Returns:
        JSON 직렬화된 검색 결과 문자열.
    """
    # Try real RAG engine
    try:
        from rag.engines.orchestrator import HybridRAGEngine

        engine = HybridRAGEngine()
        rag_result = engine.query(query, top_k=top_k)

        documents = []
        for rc in rag_result.retrieved_chunks:
            documents.append({
                "chunk_id": rc.chunk.chunk_id,
                "content": rc.chunk.content,
                "score": rc.score,
                "metadata": rc.chunk.metadata if hasattr(rc.chunk, "metadata") else {},
            })

        result: dict[str, Any] = {
            "query": query,
            "top_k": top_k,
            "answer": rag_result.answer,
            "documents": documents,
            "duration_ms": rag_result.duration_ms,
            "stub": False,
        }
        return json.dumps(result, ensure_ascii=False, default=str)
    except ImportError:
        logger.debug("HybridRAGEngine not available for document search")
    except Exception as exc:
        logger.warning("RAG engine unavailable, using stub: %s", exc)

    # Stub fallback
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
