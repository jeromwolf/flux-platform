"""MCP client for connecting to external MCP servers."""
from __future__ import annotations

import json
import logging
from typing import Any

from agent.mcp.protocol import MCPMethod, MCPRequest, MCPResponse
from agent.tools.models import ToolDefinition, ToolResult

logger = logging.getLogger(__name__)


class MCPClient:
    """MCP 서버에 연결하는 클라이언트.

    Y1 단계에서는 in-process 모드(직접 MCPServer 참조)를 지원한다.
    Y2 이후 HTTP 전송 레이어로 확장 예정.

    Example::

        server = MCPServer(tool_registry)
        client = MCPClient(server=server)
        tools = await client.list_tools()
        result = await client.call_tool("kg_query", {"query": "선박 목록"})

    Args:
        server: In-process MCPServer 인스턴스 (HTTP 미사용 시).
    """

    def __init__(self, server: Any | None = None) -> None:
        # server는 MCPServer 타입이지만 순환 임포트 방지를 위해 Any로 선언
        self._server = server
        self._request_counter = 0

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def list_tools(self) -> list[ToolDefinition]:
        """서버에 등록된 모든 도구 목록을 반환한다.

        Returns:
            ToolDefinition 목록.
        """
        response = await self._send(MCPMethod.TOOLS_LIST, {})
        if not response.success:
            logger.error("list_tools failed: %s", response.error)
            return []

        tools_data: list[dict[str, Any]] = response.result.get("tools", [])
        result: list[ToolDefinition] = []
        for item in tools_data:
            input_schema = item.get("inputSchema", {})
            properties = input_schema.get("properties", {})
            required = tuple(input_schema.get("required", []))
            defn = ToolDefinition(
                name=item["name"],
                description=item.get("description", ""),
                parameters=properties,
                required_params=required,
                category=item.get("category", "general"),
                is_dangerous=bool(item.get("is_dangerous", False)),
            )
            result.append(defn)
        return result

    async def call_tool(
        self,
        name: str,
        params: dict[str, Any] | None = None,
    ) -> ToolResult:
        """서버에서 도구를 실행하고 결과를 반환한다.

        Args:
            name: 실행할 도구 이름.
            params: 도구 입력 매개변수.

        Returns:
            ToolResult 인스턴스.
        """
        params = params or {}
        response = await self._send(
            MCPMethod.TOOLS_CALL,
            {"name": name, "arguments": params},
        )

        if not response.success:
            return ToolResult(
                tool_name=name,
                output="",
                success=False,
                error=response.error,
            )

        content = response.result.get("content", [])
        is_error = response.result.get("isError", False)
        text = content[0].get("text", "") if content else ""

        return ToolResult(
            tool_name=name,
            output=text,
            success=not is_error,
            error=text if is_error else "",
        )

    async def ping(self) -> bool:
        """서버가 살아 있는지 확인한다.

        Returns:
            연결 성공 여부.
        """
        response = await self._send(MCPMethod.PING, {})
        if not response.success:
            return False
        return response.result.get("status") == "pong"

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    async def _send(
        self,
        method: MCPMethod,
        params: dict[str, Any],
    ) -> MCPResponse:
        """요청을 서버로 전송하고 응답을 반환한다.

        현재는 in-process 모드만 지원. HTTP 모드는 미구현.

        Args:
            method: 호출할 MCP 메서드.
            params: 메서드 매개변수.

        Returns:
            MCPResponse 인스턴스.
        """
        self._request_counter += 1
        request_id = str(self._request_counter)

        request = MCPRequest(
            method=method.value,
            params=params,
            request_id=request_id,
        )

        if self._server is not None:
            # in-process 모드: 직접 handle() 호출
            return await self._server.handle(request)

        # HTTP 모드는 Y2에서 구현 예정
        return MCPResponse(
            error="HTTP transport not yet implemented",
            request_id=request_id,
        )

    def _build_json_rpc(
        self,
        method: MCPMethod,
        params: dict[str, Any],
        request_id: str,
    ) -> str:
        """JSON-RPC 요청 문자열을 생성한다. (HTTP 모드용)"""
        return json.dumps(
            {
                "jsonrpc": "2.0",
                "method": method.value,
                "params": params,
                "id": request_id,
            },
            ensure_ascii=False,
        )
