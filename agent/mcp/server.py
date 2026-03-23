"""MCP server for the agent runtime — JSON-RPC based."""
from __future__ import annotations

import json
import logging
from typing import Any

from agent.mcp.protocol import MCPMethod, MCPRequest, MCPResponse
from agent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


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

        Y1 단계에서는 정적 stub 데이터를 반환한다.
        """
        uri = params.get("uri", "")

        # stub 응답 (Y2에서 실제 Neo4j 스키마 조회로 교체 예정)
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

        if uri not in stub_contents:
            raise ValueError(f"Resource not found: {uri}")

        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": json.dumps(stub_contents[uri], ensure_ascii=False),
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
