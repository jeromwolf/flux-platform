"""Unit tests for MCP transport layer.

Covers:
    TC-TR01  InProcessTransport sends to server
    TC-TR02  InProcessTransport handles no server
    TC-TR03  HttpTransport rejects empty URL
    TC-TR04  HttpTransport with mocked urlopen
    TC-TR05  HttpTransport handles HTTP errors
    TC-TR06  HttpTransport handles connection errors
    TC-TR07  SseTransport rejects empty URL
    TC-TR08  SseTransport parses SSE events
    TC-TR09  SseTransport handles error events
    TC-TR10  All transports satisfy MCPTransport Protocol
    TC-TR11  create_transport factory -- in_process
    TC-TR12  create_transport factory -- http
    TC-TR13  create_transport factory -- sse
    TC-TR14  MCPClient with HttpTransport
    TC-TR15  MCPClient.from_url creates HTTP client
    TC-TR16  MCPClient default is InProcessTransport
"""
from __future__ import annotations

import asyncio
import io
import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from agent.mcp.client import MCPClient
from agent.mcp.protocol import MCPMethod, MCPRequest, MCPResponse
from agent.mcp.server import MCPServer
from agent.mcp.transport import (
    HttpTransport,
    InProcessTransport,
    MCPTransport,
    SseTransport,
    TransportConfig,
    create_transport,
)
from agent.tools.models import ToolDefinition
from agent.tools.registry import ToolRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro: Any) -> Any:
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


def _make_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="echo",
            description="Echo tool",
            parameters={"message": {"type": "string"}},
            required_params=("message",),
        ),
        handler=lambda message: f"echo: {message}",
    )
    return registry


def _make_server() -> MCPServer:
    return MCPServer(_make_registry())


def _make_request(
    method: str = "ping",
    params: dict[str, Any] | None = None,
    request_id: str = "1",
) -> MCPRequest:
    return MCPRequest(method=method, params=params or {}, request_id=request_id)


# ---------------------------------------------------------------------------
# TC-TR01: InProcessTransport sends to server
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestInProcessTransport:
    def test_tr01a_sends_to_server(self) -> None:
        """TC-TR01-a: InProcessTransport forwards requests to server.handle()."""
        server = _make_server()
        transport = InProcessTransport(server=server)
        request = _make_request(method=MCPMethod.PING.value)
        response = _run(transport.send(request))

        assert response.success is True
        assert response.result["status"] == "pong"

    def test_tr01b_tools_list_via_transport(self) -> None:
        """TC-TR01-b: tools/list works through InProcessTransport."""
        server = _make_server()
        transport = InProcessTransport(server=server)
        request = _make_request(method=MCPMethod.TOOLS_LIST.value)
        response = _run(transport.send(request))

        assert response.success is True
        tools = response.result["tools"]
        assert len(tools) == 1
        assert tools[0]["name"] == "echo"

    def test_tr01c_tools_call_via_transport(self) -> None:
        """TC-TR01-c: tools/call works through InProcessTransport."""
        server = _make_server()
        transport = InProcessTransport(server=server)
        request = _make_request(
            method=MCPMethod.TOOLS_CALL.value,
            params={"name": "echo", "arguments": {"message": "world"}},
        )
        response = _run(transport.send(request))

        assert response.success is True
        text = response.result["content"][0]["text"]
        assert "world" in text


# ---------------------------------------------------------------------------
# TC-TR02: InProcessTransport handles no server
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestInProcessTransportNoServer:
    def test_tr02a_no_server_returns_error(self) -> None:
        """TC-TR02-a: InProcessTransport with no server returns error response."""
        transport = InProcessTransport(server=None)
        request = _make_request()
        response = _run(transport.send(request))

        assert response.success is False
        assert "No server configured" in response.error

    def test_tr02b_close_is_noop(self) -> None:
        """TC-TR02-b: close() does not raise."""
        transport = InProcessTransport()
        transport.close()  # should not raise


# ---------------------------------------------------------------------------
# TC-TR03: HttpTransport rejects empty URL
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHttpTransportNoUrl:
    def test_tr03a_no_url_returns_error(self) -> None:
        """TC-TR03-a: HttpTransport with no URL returns error."""
        transport = HttpTransport(url="")
        request = _make_request()
        response = _run(transport.send(request))

        assert response.success is False
        assert "No URL configured" in response.error


# ---------------------------------------------------------------------------
# TC-TR04: HttpTransport with mocked urlopen
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHttpTransportMock:
    def test_tr04a_successful_request(self) -> None:
        """TC-TR04-a: HttpTransport parses a successful JSON-RPC response."""
        mock_body = json.dumps({
            "jsonrpc": "2.0",
            "id": "1",
            "result": {"status": "pong"},
        }).encode("utf-8")

        mock_response = MagicMock()
        mock_response.read.return_value = mock_body
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        transport = HttpTransport(url="http://localhost:9999/mcp")

        with patch("urllib.request.urlopen", return_value=mock_response):
            request = _make_request()
            response = _run(transport.send(request))

        assert response.success is True
        assert response.result["status"] == "pong"

    def test_tr04b_error_response_from_server(self) -> None:
        """TC-TR04-b: HttpTransport handles a JSON-RPC error response."""
        mock_body = json.dumps({
            "jsonrpc": "2.0",
            "id": "1",
            "error": {"code": -32601, "message": "Method not found"},
        }).encode("utf-8")

        mock_response = MagicMock()
        mock_response.read.return_value = mock_body

        transport = HttpTransport(url="http://localhost:9999/mcp")

        with patch("urllib.request.urlopen", return_value=mock_response):
            request = _make_request()
            response = _run(transport.send(request))

        assert response.success is False
        assert "Method not found" in response.error

    def test_tr04c_api_key_header_set(self) -> None:
        """TC-TR04-c: HttpTransport sets Authorization header when api_key provided."""
        transport = HttpTransport(url="http://localhost:9999/mcp", api_key="secret-key")
        assert transport._headers["Authorization"] == "Bearer secret-key"

    def test_tr04d_no_api_key_no_auth_header(self) -> None:
        """TC-TR04-d: HttpTransport omits Authorization header when no api_key."""
        transport = HttpTransport(url="http://localhost:9999/mcp")
        assert "Authorization" not in transport._headers


# ---------------------------------------------------------------------------
# TC-TR05: HttpTransport handles HTTP errors
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHttpTransportHttpError:
    def test_tr05a_http_error(self) -> None:
        """TC-TR05-a: HttpTransport wraps HTTPError into MCPResponse.error."""
        from urllib.error import HTTPError

        transport = HttpTransport(url="http://localhost:9999/mcp")

        with patch(
            "urllib.request.urlopen",
            side_effect=HTTPError(
                url="http://localhost:9999/mcp",
                code=500,
                msg="Internal Server Error",
                hdrs=None,  # type: ignore[arg-type]
                fp=None,
            ),
        ):
            request = _make_request()
            response = _run(transport.send(request))

        assert response.success is False
        assert "HTTP 500" in response.error


# ---------------------------------------------------------------------------
# TC-TR06: HttpTransport handles connection errors
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHttpTransportConnectionError:
    def test_tr06a_connection_refused(self) -> None:
        """TC-TR06-a: HttpTransport wraps URLError into MCPResponse.error."""
        from urllib.error import URLError

        transport = HttpTransport(url="http://localhost:9999/mcp")

        with patch(
            "urllib.request.urlopen",
            side_effect=URLError("Connection refused"),
        ):
            request = _make_request()
            response = _run(transport.send(request))

        assert response.success is False
        assert "Connection failed" in response.error


# ---------------------------------------------------------------------------
# TC-TR07: SseTransport rejects empty URL
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSseTransportNoUrl:
    def test_tr07a_no_url_returns_error(self) -> None:
        """TC-TR07-a: SseTransport with no URL returns error."""
        transport = SseTransport(url="")
        request = _make_request()
        response = _run(transport.send(request))

        assert response.success is False
        assert "No URL configured" in response.error


# ---------------------------------------------------------------------------
# TC-TR08: SseTransport parses SSE events
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSseTransportParseEvents:
    def test_tr08a_parses_result_event(self) -> None:
        """TC-TR08-a: SseTransport parses result event from SSE stream."""
        sse_lines = [
            b'data: {"type": "start", "method": "ping"}\n',
            b"\n",
            b'data: {"type": "result", "data": {"status": "pong"}}\n',
            b"\n",
            b'data: {"type": "done"}\n',
            b"\n",
        ]

        mock_response = io.BytesIO(b"".join(sse_lines))
        mock_response.read = mock_response.read  # type: ignore[assignment]

        transport = SseTransport(url="http://localhost:9999/mcp/stream")

        with patch("urllib.request.urlopen", return_value=mock_response):
            request = _make_request()
            response = _run(transport.send(request))

        assert response.success is True
        assert response.result["status"] == "pong"

    def test_tr08b_parses_chunk_events(self) -> None:
        """TC-TR08-b: SseTransport collects chunk events."""
        sse_lines = [
            b'data: {"type": "chunk", "data": "part1"}\n',
            b"\n",
            b'data: {"type": "chunk", "data": "part2"}\n',
            b"\n",
            b'data: {"type": "done"}\n',
            b"\n",
        ]

        mock_response = io.BytesIO(b"".join(sse_lines))
        transport = SseTransport(url="http://localhost:9999/mcp/stream")

        with patch("urllib.request.urlopen", return_value=mock_response):
            request = _make_request()
            response = _run(transport.send(request))

        assert response.success is True
        assert response.result["chunks"] == ["part1", "part2"]


# ---------------------------------------------------------------------------
# TC-TR09: SseTransport handles error events
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSseTransportErrorEvent:
    def test_tr09a_error_event_returns_error(self) -> None:
        """TC-TR09-a: SseTransport returns error on SSE error event."""
        sse_lines = [
            b'data: {"type": "start", "method": "ping"}\n',
            b"\n",
            b'data: {"type": "error", "message": "Tool failed"}\n',
            b"\n",
        ]

        mock_response = io.BytesIO(b"".join(sse_lines))
        transport = SseTransport(url="http://localhost:9999/mcp/stream")

        with patch("urllib.request.urlopen", return_value=mock_response):
            request = _make_request()
            response = _run(transport.send(request))

        assert response.success is False
        assert "Tool failed" in response.error

    def test_tr09b_http_error_during_sse(self) -> None:
        """TC-TR09-b: SseTransport wraps HTTP errors."""
        from urllib.error import HTTPError

        transport = SseTransport(url="http://localhost:9999/mcp/stream")

        with patch(
            "urllib.request.urlopen",
            side_effect=HTTPError(
                url="http://localhost:9999/mcp/stream",
                code=503,
                msg="Service Unavailable",
                hdrs=None,  # type: ignore[arg-type]
                fp=None,
            ),
        ):
            request = _make_request()
            response = _run(transport.send(request))

        assert response.success is False
        assert "HTTP 503" in response.error


# ---------------------------------------------------------------------------
# TC-TR10: Protocol compliance
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTransportProtocol:
    def test_tr10a_in_process_satisfies_protocol(self) -> None:
        """TC-TR10-a: InProcessTransport implements MCPTransport."""
        transport = InProcessTransport()
        assert isinstance(transport, MCPTransport)

    def test_tr10b_http_satisfies_protocol(self) -> None:
        """TC-TR10-b: HttpTransport implements MCPTransport."""
        transport = HttpTransport(url="http://example.com")
        assert isinstance(transport, MCPTransport)

    def test_tr10c_sse_satisfies_protocol(self) -> None:
        """TC-TR10-c: SseTransport implements MCPTransport."""
        transport = SseTransport(url="http://example.com")
        assert isinstance(transport, MCPTransport)


# ---------------------------------------------------------------------------
# TC-TR11..TR13: Factory tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCreateTransport:
    def test_tr11a_create_in_process_transport(self) -> None:
        """TC-TR11-a: create_transport with 'in_process' returns InProcessTransport."""
        config = TransportConfig(transport_type="in_process")
        transport = create_transport(config)
        assert isinstance(transport, InProcessTransport)

    def test_tr11b_create_in_process_with_server(self) -> None:
        """TC-TR11-b: create_transport passes server to InProcessTransport."""
        server = _make_server()
        config = TransportConfig(transport_type="in_process")
        transport = create_transport(config, server=server)
        assert isinstance(transport, InProcessTransport)
        assert transport.server is server

    def test_tr12a_create_http_transport(self) -> None:
        """TC-TR12-a: create_transport with 'http' returns HttpTransport."""
        config = TransportConfig(
            transport_type="http",
            url="http://localhost:8000/mcp",
            api_key="test-key",
            timeout=15.0,
        )
        transport = create_transport(config)
        assert isinstance(transport, HttpTransport)
        assert transport.url == "http://localhost:8000/mcp"
        assert transport.api_key == "test-key"
        assert transport.timeout == 15.0

    def test_tr13a_create_sse_transport(self) -> None:
        """TC-TR13-a: create_transport with 'sse' returns SseTransport."""
        config = TransportConfig(
            transport_type="sse",
            url="http://localhost:8000/mcp/stream",
        )
        transport = create_transport(config)
        assert isinstance(transport, SseTransport)
        assert transport.url == "http://localhost:8000/mcp/stream"


# ---------------------------------------------------------------------------
# TC-TR14..TR16: MCPClient with transport
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMCPClientWithTransport:
    def test_tr14a_client_with_http_transport(self) -> None:
        """TC-TR14-a: MCPClient accepts an explicit HttpTransport."""
        mock_body = json.dumps({
            "jsonrpc": "2.0",
            "id": "1",
            "result": {"status": "pong"},
        }).encode("utf-8")

        mock_response = MagicMock()
        mock_response.read.return_value = mock_body

        transport = HttpTransport(url="http://localhost:9999/mcp")
        client = MCPClient(transport=transport)

        with patch("urllib.request.urlopen", return_value=mock_response):
            alive = _run(client.ping())

        assert alive is True

    def test_tr15a_from_url_creates_http_client(self) -> None:
        """TC-TR15-a: MCPClient.from_url creates client with HttpTransport."""
        client = MCPClient.from_url("http://localhost:8000/mcp")
        assert isinstance(client._transport, HttpTransport)
        assert client._transport.url == "http://localhost:8000/mcp"

    def test_tr15b_from_url_creates_sse_client(self) -> None:
        """TC-TR15-b: MCPClient.from_url with sse creates SseTransport."""
        client = MCPClient.from_url(
            "http://localhost:8000/mcp/stream",
            transport_type="sse",
        )
        assert isinstance(client._transport, SseTransport)

    def test_tr15c_from_url_with_api_key(self) -> None:
        """TC-TR15-c: MCPClient.from_url passes api_key to transport."""
        client = MCPClient.from_url(
            "http://localhost:8000/mcp",
            api_key="my-token",
        )
        assert isinstance(client._transport, HttpTransport)
        assert client._transport.api_key == "my-token"

    def test_tr16a_default_is_in_process(self) -> None:
        """TC-TR16-a: MCPClient() with no args uses InProcessTransport."""
        client = MCPClient()
        assert isinstance(client._transport, InProcessTransport)
        assert client._transport.server is None

    def test_tr16b_server_param_uses_in_process(self) -> None:
        """TC-TR16-b: MCPClient(server=...) wraps with InProcessTransport."""
        server = _make_server()
        client = MCPClient(server=server)
        assert isinstance(client._transport, InProcessTransport)
        assert client._transport.server is server

    def test_tr16c_transport_param_overrides_server(self) -> None:
        """TC-TR16-c: MCPClient(transport=...) ignores server param."""
        server = _make_server()
        custom_transport = HttpTransport(url="http://example.com/mcp")
        client = MCPClient(server=server, transport=custom_transport)
        assert isinstance(client._transport, HttpTransport)

    def test_tr16d_client_close_delegates_to_transport(self) -> None:
        """TC-TR16-d: MCPClient.close() calls transport.close()."""
        mock_transport = MagicMock(spec=["send", "close"])
        client = MCPClient(transport=mock_transport)
        client.close()
        mock_transport.close.assert_called_once()
