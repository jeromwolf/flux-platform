"""MCP server for the agent runtime — JSON-RPC based."""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from agent.mcp.protocol import MCPMethod, MCPRequest, MCPResponse
from agent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema cache (module-level, shared across all MCPServer instances)
# ---------------------------------------------------------------------------

_schema_cache: dict[str, Any] = {}
_schema_cache_ts: float = 0.0
_SCHEMA_CACHE_TTL: float = 300.0  # 5 minutes


def _query_neo4j_schema() -> dict[str, Any] | None:
    """Query live Neo4j schema. Returns None on failure.

    결과는 모듈 수준 캐시에 TTL 300초(5분)로 저장된다.
    Neo4j 연결 실패 시 None을 반환하여 호출자가 stub 데이터로 폴백할 수 있도록 한다.

    Returns:
        스키마 URI → 데이터 딕셔너리, 또는 실패 시 None.
    """
    global _schema_cache, _schema_cache_ts

    now = time.time()
    if _schema_cache and (now - _schema_cache_ts) < _SCHEMA_CACHE_TTL:
        return _schema_cache

    try:
        from kg.config import get_config, get_driver

        driver = get_driver()
        cfg = get_config()
        db: str = cfg.neo4j.database

        with driver.session(database=db) as session:
            # Node labels
            labels_result = session.run(
                "CALL db.labels() YIELD label RETURN collect(label) AS labels"
            )
            labels: list[str] = labels_result.single()["labels"]

            # Relationship types
            rels_result = session.run(
                "CALL db.relationshipTypes() YIELD relationshipType"
                " RETURN collect(relationshipType) AS types"
            )
            rel_types: list[str] = rels_result.single()["types"]

            # Property keys (full catalog)
            props_result = session.run(
                "CALL db.propertyKeys() YIELD propertyKey"
                " RETURN collect(propertyKey) AS keys"
            )
            prop_keys: list[str] = props_result.single()["keys"]

        _schema_cache = {
            "kg://schema/node-labels": {"labels": sorted(labels)},
            "kg://schema/relationship-types": {"types": sorted(rel_types)},
            "kg://schema/property-keys": {"keys": sorted(prop_keys)},
        }
        _schema_cache_ts = now
        logger.info(
            "MCP schema cache refreshed: %d labels, %d rel types, %d prop keys",
            len(labels),
            len(rel_types),
            len(prop_keys),
        )
        return _schema_cache
    except Exception as exc:
        logger.debug("Neo4j schema query failed (%s), using stub data", exc)
        return None


def reset_schema_cache() -> None:
    """Reset the schema cache (for testing)."""
    global _schema_cache, _schema_cache_ts
    _schema_cache = {}
    _schema_cache_ts = 0.0


class MCPServer:
    """ToolRegistry를 MCP 프로토콜로 노출하는 서버.

    JSON-RPC 방식으로 tools/list, tools/call, resources/list,
    resources/read, ping 메서드를 구현한다.

    Example::

        server = MCPServer(tool_registry)
        response_json = await server.handle_request('{"method":"ping","id":"1"}')

    Args:
        tool_registry: 실행할 도구들이 등록된 레지스트리.
    """

    def __init__(self, tool_registry: ToolRegistry) -> None:
        self._registry = tool_registry
        # 정적 리소스 목록 (향후 KG 스키마, 온톨로지 파일 등으로 확장)
        self._resources: list[dict[str, str]] = [
            {
                "uri": "kg://schema/node-labels",
                "name": "KG Node Labels",
                "description": "Available node labels in the knowledge graph",
                "mimeType": "application/json",
            },
            {
                "uri": "kg://schema/relationship-types",
                "name": "KG Relationship Types",
                "description": "Available relationship types in the knowledge graph",
                "mimeType": "application/json",
            },
            {
                "uri": "kg://schema/property-keys",
                "name": "KG Property Keys",
                "description": "Property keys used in the knowledge graph",
                "mimeType": "application/json",
            },
            {
                "uri": "maritime://ontology/vessel-types",
                "name": "Maritime Vessel Types",
                "description": "KRISO vessel type classification",
                "mimeType": "application/json",
            },
        ]

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def handle(self, request: MCPRequest) -> MCPResponse:
        """MCPRequest를 처리하고 MCPResponse를 반환한다.

        Args:
            request: 처리할 MCP 요청.

        Returns:
            처리 결과가 담긴 MCPResponse.
        """
        dispatch = {
            MCPMethod.TOOLS_LIST: self._handle_tools_list,
            MCPMethod.TOOLS_CALL: self._handle_tools_call,
            MCPMethod.RESOURCES_LIST: self._handle_resources_list,
            MCPMethod.RESOURCES_READ: self._handle_resources_read,
            MCPMethod.PING: self._handle_ping,
        }

        # MCPMethod enum 값이나 문자열 모두 수용
        method_key: MCPMethod | None = None
        for m in MCPMethod:
            if m.value == request.method or m == request.method:
                method_key = m
                break

        if method_key is None:
            return MCPResponse(
                error=f"Method not found: {request.method}",
                request_id=request.request_id,
            )

        handler_fn = dispatch[method_key]
        try:
            result = await handler_fn(request.params)
            return MCPResponse(result=result, request_id=request.request_id)
        except Exception as exc:
            logger.error("MCPServer error for method '%s': %s", request.method, exc)
            return MCPResponse(
                error=str(exc),
                request_id=request.request_id,
            )

    async def handle_request(self, raw_json: str) -> str:
        """JSON-RPC 문자열을 받아 처리하고 JSON 응답 문자열을 반환한다.

        Args:
            raw_json: JSON-RPC 형식의 요청 문자열.

        Returns:
            JSON-RPC 형식의 응답 문자열.
        """
        try:
            data: dict[str, Any] = json.loads(raw_json)
        except json.JSONDecodeError:
            return json.dumps(
                {"error": {"code": -32700, "message": "Parse error"}, "id": None},
                ensure_ascii=False,
            )

        request_id = str(data.get("id", ""))
        method = data.get("method", "")
        params = data.get("params", {})
        if not isinstance(params, dict):
            params = {}

        mcp_request = MCPRequest(
            method=method,
            params=params,
            request_id=request_id,
        )
        mcp_response = await self.handle(mcp_request)
        return self._serialize_response(mcp_response, data.get("id"))

    # ------------------------------------------------------------------
    # Method handlers
    # ------------------------------------------------------------------

    async def _handle_tools_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """tools/list: 등록된 모든 도구를 JSON Schema 형태로 반환."""
        tools = []
        for defn in self._registry.list_tools():
            tool_schema: dict[str, Any] = {
                "name": defn.name,
                "description": defn.description,
                "inputSchema": {
                    "type": "object",
                    "properties": defn.parameters,
                    "required": list(defn.required_params),
                },
            }
            if defn.category != "general":
                tool_schema["category"] = defn.category
            if defn.is_dangerous:
                tool_schema["is_dangerous"] = True
            tools.append(tool_schema)
        return {"tools": tools}

    async def _handle_tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        """tools/call: 도구를 실행하고 결과를 반환."""
        name = params.get("name", "")
        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            arguments = {}

        result = self._registry.execute(name, arguments)

        if result.success:
            return {
                "content": [
                    {"type": "text", "text": result.output}
                ],
            }
        else:
            return {
                "content": [
                    {"type": "text", "text": f"Error: {result.error}"}
                ],
                "isError": True,
            }

    async def _handle_resources_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """resources/list: 사용 가능한 리소스 목록을 반환."""
        return {"resources": self._resources}

    async def _handle_resources_read(self, params: dict[str, Any]) -> dict[str, Any]:
        """resources/read: 특정 리소스를 읽어 반환.

        Neo4j에서 라이브 스키마를 조회한 뒤 URI에 맞는 리소스를 반환한다.
        Neo4j를 사용할 수 없을 경우 정적 stub 데이터로 폴백한다.
        알 수 없는 URI는 error 키를 포함한 contents를 반환한다.
        """
        uri = params.get("uri", "")

        # stub 데이터 (Neo4j 폴백 + maritime 온톨로지 등 정적 리소스)
        stub_contents: dict[str, Any] = {
            "kg://schema/node-labels": {
                "labels": ["Vessel", "Port", "Route", "Cargo", "Document"]
            },
            "kg://schema/relationship-types": {
                "types": ["DOCKED_AT", "SAILED_TO", "CARRIES", "PART_OF"]
            },
            "maritime://ontology/vessel-types": {
                "types": [
                    "cargo_ship", "tanker", "container_ship",
                    "bulk_carrier", "passenger_ship", "fishing_vessel",
                ]
            },
        }

        # 라이브 Neo4j 스키마 조회 (실패 시 None)
        live_schema = _query_neo4j_schema()

        # stub를 기본으로, 라이브 데이터로 덮어쓴다
        schema_data: dict[str, Any] = {**stub_contents}
        if live_schema:
            schema_data.update(live_schema)

        if uri in schema_data:
            content = schema_data[uri]
        else:
            content = {"error": f"Resource not found: {uri}"}

        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": json.dumps(content, ensure_ascii=False),
                }
            ]
        }

    async def _handle_ping(self, params: dict[str, Any]) -> dict[str, Any]:
        """ping: 서버 상태 확인."""
        return {"status": "pong", "tool_count": self._registry.tool_count}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize_response(
        response: MCPResponse,
        original_id: Any,
    ) -> str:
        """MCPResponse를 JSON-RPC 문자열로 직렬화."""
        payload: dict[str, Any] = {}
        if original_id is not None:
            payload["id"] = original_id

        if response.error:
            payload["error"] = {"code": -32000, "message": response.error}
        else:
            payload["result"] = response.result

        return json.dumps(payload, ensure_ascii=False)
