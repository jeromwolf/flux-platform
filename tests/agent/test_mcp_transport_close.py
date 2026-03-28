"""Tests for MCP transport close() methods.

TC-TC01: InProcessTransport close releases server reference.
TC-TC02: HttpTransport close marks transport as closed.
TC-TC03: SseTransport close marks transport as closed.
TC-TC04: Sending on closed transport returns error.
"""
from __future__ import annotations

import pytest

from agent.mcp.protocol import MCPRequest, MCPResponse
from agent.mcp.transport import (
    HttpTransport,
    InProcessTransport,
    SseTransport,
    create_transport,
    TransportConfig,
)


@pytest.mark.unit
class TestInProcessTransportClose:
    """TC-TC01: InProcessTransport.close() behavior."""

    def test_tc01a_close_releases_server(self) -> None:
        """TC-TC01-a: close() sets server to None."""
        transport = InProcessTransport(server="mock-server")
        assert transport.server is not None
        transport.close()
        assert transport.server is None

    def test_tc01b_close_idempotent(self) -> None:
        """TC-TC01-b: Calling close() twice does not raise."""
        transport = InProcessTransport(server="mock")
        transport.close()
        transport.close()  # Should not raise
        assert transport.server is None


@pytest.mark.unit
class TestHttpTransportClose:
    """TC-TC02: HttpTransport.close() behavior."""

    def test_tc02a_close_marks_closed(self) -> None:
        """TC-TC02-a: close() sets _closed flag to True."""
        transport = HttpTransport(url="http://localhost:8080")
        assert transport._closed is False
        transport.close()
        assert transport._closed is True

    def test_tc02b_close_idempotent(self) -> None:
        """TC-TC02-b: Calling close() twice does not raise."""
        transport = HttpTransport(url="http://localhost:8080")
        transport.close()
        transport.close()
        assert transport._closed is True

    @pytest.mark.asyncio
    async def test_tc02c_send_after_close_returns_error(self) -> None:
        """TC-TC02-c: Sending on closed transport returns error response."""
        transport = HttpTransport(url="http://localhost:8080")
        transport.close()
        req = MCPRequest(method="test", params={}, request_id="req-1")
        resp = await transport.send(req)
        assert resp.error is not None
        assert "closed" in resp.error.lower()


@pytest.mark.unit
class TestSseTransportClose:
    """TC-TC03: SseTransport.close() behavior."""

    def test_tc03a_close_marks_closed(self) -> None:
        """TC-TC03-a: close() sets _closed flag to True."""
        transport = SseTransport(url="http://localhost:8080")
        assert transport._closed is False
        transport.close()
        assert transport._closed is True

    def test_tc03b_close_idempotent(self) -> None:
        """TC-TC03-b: Calling close() twice does not raise."""
        transport = SseTransport(url="http://localhost:8080")
        transport.close()
        transport.close()
        assert transport._closed is True

    @pytest.mark.asyncio
    async def test_tc03c_send_after_close_returns_error(self) -> None:
        """TC-TC03-c: Sending on closed transport returns error response."""
        transport = SseTransport(url="http://localhost:8080")
        transport.close()
        req = MCPRequest(method="test", params={}, request_id="req-2")
        resp = await transport.send(req)
        assert resp.error is not None
        assert "closed" in resp.error.lower()


@pytest.mark.unit
class TestTransportFactory:
    """TC-TC04: create_transport factory."""

    def test_tc04a_creates_in_process_by_default(self) -> None:
        """TC-TC04-a: Default transport_type creates InProcessTransport."""
        config = TransportConfig()
        t = create_transport(config)
        assert isinstance(t, InProcessTransport)

    def test_tc04b_creates_http_transport(self) -> None:
        """TC-TC04-b: 'http' transport_type creates HttpTransport."""
        config = TransportConfig(transport_type="http", url="http://example.com")
        t = create_transport(config)
        assert isinstance(t, HttpTransport)

    def test_tc04c_creates_sse_transport(self) -> None:
        """TC-TC04-c: 'sse' transport_type creates SseTransport."""
        config = TransportConfig(transport_type="sse", url="http://example.com")
        t = create_transport(config)
        assert isinstance(t, SseTransport)
