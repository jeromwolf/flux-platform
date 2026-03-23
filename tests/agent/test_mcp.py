"""Unit tests for MCP protocol, server, and client.

Covers:
    TC-MCP01  MCPRequest/MCPResponse construction
    TC-MCP02  MCPServer tools/list returns registered tools
    TC-MCP03  MCPServer tools/call executes tool and returns result
    TC-MCP04  MCPServer handles unknown method gracefully
    TC-MCP05  MCPServer ping returns pong
    TC-MCP06  MCPClient list_tools (in-process mode)
    TC-MCP07  MCPClient call_tool (in-process mode)
    TC-MCP08  JSON-RPC request/response round-trip
"""

from __future__ import annotations

import asyncio
import json

import pytest

from agent.mcp.protocol import MCPHandler, MCPMethod, MCPRequest, MCPResponse
from agent.mcp.server import MCPServer
from agent.mcp.client import MCPClient
from agent.tools.models import ToolDefinition
from agent.tools.registry import ToolRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_registry_with_echo() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="echo",
            description="Echoes the message",
            parameters={"message": {"type": "string"}},
            required_params=("message",),
        ),
        handler=lambda message: f"echo: {message}",
    )
    return registry


def _make_server() -> MCPServer:
    return MCPServer(_make_registry_with_echo())


def _run(coro):
    """asyncio.run 래퍼 (pytest-asyncio 없이 비동기 테스트 실행)."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# TC-MCP01: MCPRequest / MCPResponse construction
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMCPProtocol:
    """TC-MCP01: MCPRequest/MCPResponse 생성 및 속성 검증."""

    def test_mcp01a_request_construction(self) -> None:
        """TC-MCP01-a: MCPRequest가 method, params, request_id를 올바르게 저장."""
        req = MCPRequest(
            method=MCPMethod.TOOLS_LIST.value,
            params={"filter": "kg"},
            request_id="req-001",
        )
        assert req.method == MCPMethod.TOOLS_LIST.value
        assert req.params == {"filter": "kg"}
        assert req.request_id == "req-001"

    def test_mcp01b_request_defaults(self) -> None:
        """TC-MCP01-b: MCPRequest 기본값 확인."""
        req = MCPRequest(method="ping")
        assert req.params == {}
        assert req.request_id == ""

    def test_mcp01c_response_success_true_when_no_error(self) -> None:
        """TC-MCP01-c: MCPResponse.success == True when error is empty."""
        resp = MCPResponse(result={"status": "ok"})
        assert resp.success is True
        assert resp.error == ""

    def test_mcp01d_response_success_false_when_error(self) -> None:
        """TC-MCP01-d: MCPResponse.success == False when error is set."""
        resp = MCPResponse(error="something went wrong")
        assert resp.success is False
        assert resp.result is None

    def test_mcp01e_request_is_frozen(self) -> None:
        """TC-MCP01-e: MCPRequest는 frozen dataclass 이므로 변경 불가."""
        import dataclasses

        req = MCPRequest(method="ping")
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            req.method = "changed"  # type: ignore[misc]

    def test_mcp01f_response_is_frozen(self) -> None:
        """TC-MCP01-f: MCPResponse는 frozen dataclass 이므로 변경 불가."""
        import dataclasses

        resp = MCPResponse(result="ok")
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            resp.result = "changed"  # type: ignore[misc]

    def test_mcp01g_mcp_method_enum_values(self) -> None:
        """TC-MCP01-g: MCPMethod enum 값이 올바른 문자열인지 확인."""
        assert MCPMethod.TOOLS_LIST.value == "tools/list"
        assert MCPMethod.TOOLS_CALL.value == "tools/call"
        assert MCPMethod.RESOURCES_LIST.value == "resources/list"
        assert MCPMethod.RESOURCES_READ.value == "resources/read"
        assert MCPMethod.PING.value == "ping"


# ---------------------------------------------------------------------------
# TC-MCP02: MCPServer tools/list
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMCPServerToolsList:
    """TC-MCP02: MCPServer tools/list 응답 검증."""

    def test_mcp02a_tools_list_returns_registered_tool(self) -> None:
        """TC-MCP02-a: tools/list 응답에 등록된 도구가 포함됨."""
        server = _make_server()
        request = MCPRequest(method=MCPMethod.TOOLS_LIST.value, request_id="r1")
        response = _run(server.handle(request))

        assert response.success is True
        tools = response.result.get("tools", [])
        assert len(tools) == 1
        assert tools[0]["name"] == "echo"

    def test_mcp02b_tool_has_input_schema(self) -> None:
        """TC-MCP02-b: 반환된 도구에 inputSchema가 있음."""
        server = _make_server()
        request = MCPRequest(method=MCPMethod.TOOLS_LIST.value)
        response = _run(server.handle(request))

        tool = response.result["tools"][0]
        assert "inputSchema" in tool
        assert "properties" in tool["inputSchema"]
        assert "required" in tool["inputSchema"]

    def test_mcp02c_empty_registry_returns_empty_list(self) -> None:
        """TC-MCP02-c: 빈 레지스트리에서 tools/list는 빈 목록 반환."""
        server = MCPServer(ToolRegistry())
        request = MCPRequest(method=MCPMethod.TOOLS_LIST.value)
        response = _run(server.handle(request))

        assert response.success is True
        assert response.result["tools"] == []


# ---------------------------------------------------------------------------
# TC-MCP03: MCPServer tools/call
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMCPServerToolsCall:
    """TC-MCP03: MCPServer tools/call 실행 검증."""

    def test_mcp03a_tools_call_returns_tool_output(self) -> None:
        """TC-MCP03-a: tools/call 응답에 도구 실행 결과가 포함됨."""
        server = _make_server()
        request = MCPRequest(
            method=MCPMethod.TOOLS_CALL.value,
            params={"name": "echo", "arguments": {"message": "hello"}},
            request_id="r2",
        )
        response = _run(server.handle(request))

        assert response.success is True
        content = response.result.get("content", [])
        assert len(content) > 0
        assert "hello" in content[0]["text"]

    def test_mcp03b_tools_call_unknown_tool_returns_is_error(self) -> None:
        """TC-MCP03-b: 존재하지 않는 도구 호출 시 isError 플래그가 True."""
        server = _make_server()
        request = MCPRequest(
            method=MCPMethod.TOOLS_CALL.value,
            params={"name": "nonexistent", "arguments": {}},
        )
        response = _run(server.handle(request))

        assert response.success is True  # MCP 레이어는 성공, 도구 레이어가 실패
        assert response.result.get("isError") is True

    def test_mcp03c_tools_call_missing_required_param_returns_is_error(self) -> None:
        """TC-MCP03-c: 필수 파라미터 누락 시 isError 플래그가 True."""
        server = _make_server()
        request = MCPRequest(
            method=MCPMethod.TOOLS_CALL.value,
            params={"name": "echo", "arguments": {}},  # message 누락
        )
        response = _run(server.handle(request))

        assert response.result.get("isError") is True


# ---------------------------------------------------------------------------
# TC-MCP04: MCPServer handles unknown method
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMCPServerUnknownMethod:
    """TC-MCP04: MCPServer 알 수 없는 메서드 처리."""

    def test_mcp04a_unknown_method_returns_error(self) -> None:
        """TC-MCP04-a: 알 수 없는 메서드 호출 시 error가 설정됨."""
        server = _make_server()
        request = MCPRequest(method="nonexistent/method")
        response = _run(server.handle(request))

        assert response.success is False
        assert "nonexistent/method" in response.error

    def test_mcp04b_empty_method_returns_error(self) -> None:
        """TC-MCP04-b: 빈 메서드 호출 시 error가 설정됨."""
        server = _make_server()
        request = MCPRequest(method="")
        response = _run(server.handle(request))

        assert response.success is False


# ---------------------------------------------------------------------------
# TC-MCP05: MCPServer ping
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMCPServerPing:
    """TC-MCP05: MCPServer ping 헬스 체크."""

    def test_mcp05a_ping_returns_pong_status(self) -> None:
        """TC-MCP05-a: ping 메서드가 status='pong' 응답 반환."""
        server = _make_server()
        request = MCPRequest(method=MCPMethod.PING.value)
        response = _run(server.handle(request))

        assert response.success is True
        assert response.result["status"] == "pong"

    def test_mcp05b_ping_includes_tool_count(self) -> None:
        """TC-MCP05-b: ping 응답에 tool_count가 포함됨."""
        server = _make_server()
        request = MCPRequest(method=MCPMethod.PING.value)
        response = _run(server.handle(request))

        assert "tool_count" in response.result
        assert response.result["tool_count"] == 1

    def test_mcp05c_ping_request_id_echoed(self) -> None:
        """TC-MCP05-c: request_id가 응답에 그대로 반환됨."""
        server = _make_server()
        request = MCPRequest(method=MCPMethod.PING.value, request_id="test-id-42")
        response = _run(server.handle(request))

        assert response.request_id == "test-id-42"


# ---------------------------------------------------------------------------
# TC-MCP06: MCPClient list_tools (in-process)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMCPClientListTools:
    """TC-MCP06: MCPClient list_tools (in-process 모드)."""

    def test_mcp06a_list_tools_returns_tool_definitions(self) -> None:
        """TC-MCP06-a: list_tools()가 ToolDefinition 목록을 반환."""
        server = _make_server()
        client = MCPClient(server=server)
        tools = _run(client.list_tools())

        assert len(tools) == 1
        assert tools[0].name == "echo"

    def test_mcp06b_list_tools_returns_tool_definition_type(self) -> None:
        """TC-MCP06-b: list_tools()가 ToolDefinition 타입 목록 반환."""
        server = _make_server()
        client = MCPClient(server=server)
        tools = _run(client.list_tools())

        for tool in tools:
            assert isinstance(tool, ToolDefinition)

    def test_mcp06c_list_tools_empty_when_no_tools(self) -> None:
        """TC-MCP06-c: 도구가 없을 때 list_tools()는 빈 목록 반환."""
        server = MCPServer(ToolRegistry())
        client = MCPClient(server=server)
        tools = _run(client.list_tools())

        assert tools == []


# ---------------------------------------------------------------------------
# TC-MCP07: MCPClient call_tool (in-process)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMCPClientCallTool:
    """TC-MCP07: MCPClient call_tool (in-process 모드)."""

    def test_mcp07a_call_tool_returns_tool_result(self) -> None:
        """TC-MCP07-a: call_tool()이 ToolResult를 반환하고 성공함."""
        from agent.tools.models import ToolResult

        server = _make_server()
        client = MCPClient(server=server)
        result = _run(client.call_tool("echo", {"message": "world"}))

        assert isinstance(result, ToolResult)
        assert result.success is True
        assert "world" in result.output

    def test_mcp07b_call_tool_unknown_returns_failure(self) -> None:
        """TC-MCP07-b: 존재하지 않는 도구 호출 시 success=False 반환."""
        server = _make_server()
        client = MCPClient(server=server)
        result = _run(client.call_tool("nonexistent"))

        assert result.success is False

    def test_mcp07c_call_tool_without_server_returns_failure(self) -> None:
        """TC-MCP07-c: 서버 없이 call_tool() 호출 시 error 반환."""
        client = MCPClient(server=None)
        result = _run(client.call_tool("echo", {"message": "test"}))

        assert result.success is False

    def test_mcp07d_ping_returns_true(self) -> None:
        """TC-MCP07-d: ping()이 서버 연결 확인 후 True 반환."""
        server = _make_server()
        client = MCPClient(server=server)
        alive = _run(client.ping())

        assert alive is True

    def test_mcp07e_ping_without_server_returns_false(self) -> None:
        """TC-MCP07-e: 서버 없이 ping() 호출 시 False 반환."""
        client = MCPClient(server=None)
        alive = _run(client.ping())

        assert alive is False


# ---------------------------------------------------------------------------
# TC-MCP08: JSON-RPC round-trip
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMCPJsonRpc:
    """TC-MCP08: JSON-RPC 요청/응답 라운드트립."""

    def test_mcp08a_ping_json_rpc_round_trip(self) -> None:
        """TC-MCP08-a: JSON-RPC ping 라운드트립."""
        server = _make_server()
        raw = json.dumps({"jsonrpc": "2.0", "method": "ping", "params": {}, "id": "1"})
        response_str = _run(server.handle_request(raw))
        data = json.loads(response_str)

        assert "result" in data
        assert data["result"]["status"] == "pong"
        assert data["id"] == "1"

    def test_mcp08b_tools_list_json_rpc_round_trip(self) -> None:
        """TC-MCP08-b: JSON-RPC tools/list 라운드트립."""
        server = _make_server()
        raw = json.dumps({"method": "tools/list", "id": 42})
        response_str = _run(server.handle_request(raw))
        data = json.loads(response_str)

        assert "result" in data
        assert "tools" in data["result"]
        assert data["id"] == 42

    def test_mcp08c_tools_call_json_rpc_round_trip(self) -> None:
        """TC-MCP08-c: JSON-RPC tools/call 라운드트립."""
        server = _make_server()
        raw = json.dumps({
            "method": "tools/call",
            "params": {"name": "echo", "arguments": {"message": "hi"}},
            "id": "req-3",
        })
        response_str = _run(server.handle_request(raw))
        data = json.loads(response_str)

        assert "result" in data
        content = data["result"].get("content", [])
        assert len(content) > 0
        assert "hi" in content[0]["text"]

    def test_mcp08d_invalid_json_returns_parse_error(self) -> None:
        """TC-MCP08-d: 잘못된 JSON 입력 시 parse error 반환."""
        server = _make_server()
        response_str = _run(server.handle_request("{invalid json}"))
        data = json.loads(response_str)

        assert "error" in data

    def test_mcp08e_unknown_method_json_rpc_returns_error(self) -> None:
        """TC-MCP08-e: 알 수 없는 메서드 JSON-RPC 요청 시 error 반환."""
        server = _make_server()
        raw = json.dumps({"method": "unknown/method", "id": "x"})
        response_str = _run(server.handle_request(raw))
        data = json.loads(response_str)

        assert "error" in data

    def test_mcp08f_resources_list_json_rpc_round_trip(self) -> None:
        """TC-MCP08-f: JSON-RPC resources/list 라운드트립."""
        server = _make_server()
        raw = json.dumps({"method": "resources/list", "id": "r1"})
        response_str = _run(server.handle_request(raw))
        data = json.loads(response_str)

        assert "result" in data
        assert "resources" in data["result"]
        assert isinstance(data["result"]["resources"], list)

    def test_mcp08g_mcp_handler_protocol_satisfied(self) -> None:
        """TC-MCP08-g: MCPServer가 MCPHandler 프로토콜을 만족함."""
        server = _make_server()
        assert isinstance(server, MCPHandler)
