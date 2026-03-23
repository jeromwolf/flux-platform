"""Unit tests for the MCP JSON-RPC API endpoint.

Covers:
    TC-EP01  POST /mcp/ -- tools/list
    TC-EP02  POST /mcp/ -- tools/call
    TC-EP03  POST /mcp/ -- ping
    TC-EP04  POST /mcp/ -- unknown method returns error
    TC-EP05  POST /mcp/stream -- returns SSE
    TC-EP06  POST /mcp/stream -- error event
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_client() -> TestClient:
    """Create a TestClient for the MCP endpoint.

    We build a minimal FastAPI app including only the MCP router
    to avoid needing full Neo4j/Keycloak infrastructure.
    """
    from fastapi import FastAPI

    from kg.api.routes.mcp_endpoint import router as mcp_router

    app = FastAPI()
    app.include_router(mcp_router, prefix="/api/v1")
    return TestClient(app)


# ---------------------------------------------------------------------------
# TC-EP01: tools/list
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMCPEndpointToolsList:
    def test_ep01a_tools_list_returns_tools(self) -> None:
        """TC-EP01-a: POST /mcp/ with tools/list returns tool definitions."""
        client = _get_client()
        resp = client.post(
            "/api/v1/mcp/",
            json={
                "jsonrpc": "2.0",
                "method": "tools/list",
                "params": {},
                "id": "1",
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "result" in data
        assert "tools" in data["result"]
        assert isinstance(data["result"]["tools"], list)
        assert len(data["result"]["tools"]) > 0

    def test_ep01b_tools_have_names_and_schemas(self) -> None:
        """TC-EP01-b: Each tool has name and inputSchema."""
        client = _get_client()
        resp = client.post(
            "/api/v1/mcp/",
            json={"method": "tools/list", "params": {}, "id": "2"},
        )

        data = resp.json()
        for tool in data["result"]["tools"]:
            assert "name" in tool
            assert "inputSchema" in tool


# ---------------------------------------------------------------------------
# TC-EP02: tools/call
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMCPEndpointToolsCall:
    def test_ep02a_tools_call_vessel_search(self) -> None:
        """TC-EP02-a: tools/call executes a tool and returns content."""
        client = _get_client()
        resp = client.post(
            "/api/v1/mcp/",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "vessel_search",
                    "arguments": {"query": "BUSAN"},
                },
                "id": "3",
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "result" in data
        content = data["result"]["content"]
        assert isinstance(content, list)
        assert len(content) > 0
        # The text should contain valid JSON
        text = content[0]["text"]
        parsed = json.loads(text)
        assert "query" in parsed

    def test_ep02b_tools_call_unknown_tool(self) -> None:
        """TC-EP02-b: tools/call with unknown tool returns isError."""
        client = _get_client()
        resp = client.post(
            "/api/v1/mcp/",
            json={
                "method": "tools/call",
                "params": {"name": "nonexistent_tool", "arguments": {}},
                "id": "4",
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["result"].get("isError") is True


# ---------------------------------------------------------------------------
# TC-EP03: ping
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMCPEndpointPing:
    def test_ep03a_ping_returns_pong(self) -> None:
        """TC-EP03-a: POST /mcp/ with ping returns pong."""
        client = _get_client()
        resp = client.post(
            "/api/v1/mcp/",
            json={"method": "ping", "params": {}, "id": "5"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["status"] == "pong"
        assert data["result"]["tool_count"] > 0

    def test_ep03b_ping_echoes_request_id(self) -> None:
        """TC-EP03-b: Response id matches request id."""
        client = _get_client()
        resp = client.post(
            "/api/v1/mcp/",
            json={"method": "ping", "params": {}, "id": "test-42"},
        )

        data = resp.json()
        assert data["id"] == "test-42"


# ---------------------------------------------------------------------------
# TC-EP04: unknown method
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMCPEndpointUnknownMethod:
    def test_ep04a_unknown_method_returns_error(self) -> None:
        """TC-EP04-a: Unknown method returns 400 with error."""
        client = _get_client()
        resp = client.post(
            "/api/v1/mcp/",
            json={"method": "unknown/method", "params": {}, "id": "6"},
        )

        assert resp.status_code == 400
        data = resp.json()
        assert "error" in data
        assert "Unknown method" in data["error"]["message"]


# ---------------------------------------------------------------------------
# TC-EP05: SSE stream
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMCPEndpointStream:
    def test_ep05a_stream_returns_sse_events(self) -> None:
        """TC-EP05-a: POST /mcp/stream returns SSE events."""
        client = _get_client()
        resp = client.post(
            "/api/v1/mcp/stream",
            json={"method": "ping", "params": {}, "id": "7"},
        )

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

        # Parse SSE events from response body
        events = []
        for line in resp.text.split("\n"):
            line = line.strip()
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))

        # Expect: start, result, done
        assert len(events) >= 2
        event_types = [e["type"] for e in events]
        assert "start" in event_types
        assert "done" in event_types

        # Find the result event
        result_events = [e for e in events if e["type"] == "result"]
        assert len(result_events) == 1
        assert result_events[0]["data"]["status"] == "pong"

    def test_ep05b_stream_tools_call(self) -> None:
        """TC-EP05-b: SSE stream works with tools/call."""
        client = _get_client()
        resp = client.post(
            "/api/v1/mcp/stream",
            json={
                "method": "tools/call",
                "params": {
                    "name": "kg_schema",
                    "arguments": {},
                },
                "id": "8",
            },
        )

        assert resp.status_code == 200
        events = []
        for line in resp.text.split("\n"):
            line = line.strip()
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))

        result_events = [e for e in events if e["type"] == "result"]
        assert len(result_events) == 1
        # The result data should have content with tool output
        assert "content" in result_events[0]["data"]


# ---------------------------------------------------------------------------
# TC-EP06: SSE stream error
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMCPEndpointStreamError:
    def test_ep06a_stream_unknown_method_returns_400(self) -> None:
        """TC-EP06-a: SSE stream with unknown method returns 400."""
        client = _get_client()
        resp = client.post(
            "/api/v1/mcp/stream",
            json={"method": "bad/method", "params": {}, "id": "9"},
        )

        assert resp.status_code == 400
        data = resp.json()
        assert "error" in data
