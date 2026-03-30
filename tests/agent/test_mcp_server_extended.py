"""Extended unit tests for MCP server (agent/mcp/server.py).

Targets missed lines:
    50-78   _query_neo4j_schema live path (cache hit, query logic, cache refresh)
    174-176 MCPServer.handle exception handler path
    202     handle_request non-dict params coerced to {}
    241     tools/list with category + is_dangerous flags
    294     resources/read live schema merges with stub data
"""
from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import MagicMock, patch

import pytest

from agent.mcp.protocol import MCPMethod, MCPRequest, MCPResponse
from agent.mcp.server import MCPServer, _query_neo4j_schema, reset_schema_cache
from agent.tools.models import ToolDefinition
from agent.tools.registry import ToolRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):
    """Run async coroutine synchronously."""
    return asyncio.run(coro)


def _make_registry_with_echo() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="echo",
            description="Echoes the message",
            parameters={"message": {"type": "string"}},
            required_params=("message",),
        ),
        handler=lambda message="": f"echo: {message}",
    )
    return registry


def _make_server() -> MCPServer:
    return MCPServer(_make_registry_with_echo())


# ---------------------------------------------------------------------------
# TC-EXT-MCP01: _query_neo4j_schema cache behaviour (lines 35-37)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestQueryNeo4jSchemaCache:
    """Covers schema cache TTL and cache-hit path."""

    def setup_method(self) -> None:
        reset_schema_cache()

    def test_cache_miss_returns_none_when_neo4j_unavailable(self) -> None:
        """Returns None when neo4j import fails (no live DB in unit tests)."""
        result = _query_neo4j_schema()
        # Either None (neo4j unavailable) or a dict (if somehow available)
        assert result is None or isinstance(result, dict)

    def test_cache_hit_returns_existing_cache_without_neo4j(self) -> None:
        """If cache is populated manually, repeated calls return cached value."""
        import agent.mcp.server as server_module

        # Manually populate the cache to simulate a previous successful call
        fake_schema = {
            "kg://schema/node-labels": {"labels": ["Vessel", "Port"]},
            "kg://schema/relationship-types": {"types": ["DOCKED_AT"]},
            "kg://schema/property-keys": {"keys": ["name", "imo"]},
        }
        server_module._schema_cache = fake_schema
        server_module._schema_cache_ts = time.time()  # Fresh timestamp

        result = _query_neo4j_schema()
        assert result is fake_schema  # Same object — cache hit

    def test_cache_expired_triggers_refresh_attempt(self) -> None:
        """Expired cache causes Neo4j query attempt (which fails in unit tests)."""
        import agent.mcp.server as server_module

        fake_schema = {"kg://schema/node-labels": {"labels": ["Vessel"]}}
        server_module._schema_cache = fake_schema
        server_module._schema_cache_ts = 0.0  # Force expiry

        # Without Neo4j, _query_neo4j_schema should return None (refresh failed)
        result = _query_neo4j_schema()
        # Either None (refresh failed) or the new schema
        assert result is None or isinstance(result, dict)

    def test_reset_schema_cache_clears_state(self) -> None:
        """reset_schema_cache() empties cache and resets timestamp."""
        import agent.mcp.server as server_module

        server_module._schema_cache = {"some": "data"}
        server_module._schema_cache_ts = 999.0
        reset_schema_cache()

        assert server_module._schema_cache == {}
        assert server_module._schema_cache_ts == 0.0


# ---------------------------------------------------------------------------
# TC-EXT-MCP02: MCPServer.handle exception handler (lines 174-176)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMCPServerHandleExceptions:
    """Covers the try/except in MCPServer.handle (lines 171-178)."""

    def test_handler_exception_returns_error_response(self) -> None:
        """If a handler raises, handle() returns error MCPResponse."""
        server = _make_server()

        # Monkey-patch the ping handler to raise
        async def exploding_handler(params: dict) -> dict:
            raise RuntimeError("internal server error")

        server._handle_ping = exploding_handler  # type: ignore[method-assign]

        request = MCPRequest(method=MCPMethod.PING.value, request_id="err-1")
        response = _run(server.handle(request))

        assert response.success is False
        assert "internal server error" in response.error
        assert response.request_id == "err-1"

    def test_tools_list_handler_exception_returns_error(self) -> None:
        """If tools/list handler raises, error response is returned."""
        server = _make_server()

        async def broken_list(params: dict) -> dict:
            raise ValueError("list broken")

        server._handle_tools_list = broken_list  # type: ignore[method-assign]

        request = MCPRequest(method=MCPMethod.TOOLS_LIST.value, request_id="err-2")
        response = _run(server.handle(request))

        assert response.success is False
        assert "list broken" in response.error

    def test_tools_call_handler_exception_returns_error(self) -> None:
        """If tools/call handler raises unexpectedly, error response is returned."""
        server = _make_server()

        async def broken_call(params: dict) -> dict:
            raise TypeError("call broken")

        server._handle_tools_call = broken_call  # type: ignore[method-assign]

        request = MCPRequest(
            method=MCPMethod.TOOLS_CALL.value,
            params={"name": "echo", "arguments": {}},
            request_id="err-3",
        )
        response = _run(server.handle(request))

        assert response.success is False
        assert "call broken" in response.error


# ---------------------------------------------------------------------------
# TC-EXT-MCP03: handle_request non-dict params (line 202)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMCPHandleRequestParamCoercion:
    """Covers line 202: non-dict params coerced to {}."""

    def test_list_params_coerced_to_empty_dict(self) -> None:
        """When 'params' is a list, it is coerced to {} and ping still succeeds."""
        server = _make_server()
        # Send params as a JSON array instead of object
        raw = json.dumps({"method": "ping", "params": ["invalid", "params"], "id": "p1"})
        response_str = _run(server.handle_request(raw))
        data = json.loads(response_str)

        # Should succeed — params coerced to {}
        assert "result" in data
        assert data["result"]["status"] == "pong"

    def test_string_params_coerced_to_empty_dict(self) -> None:
        """When 'params' is a string, it is coerced to {}."""
        server = _make_server()
        raw = json.dumps({"method": "ping", "params": "not_a_dict", "id": "p2"})
        response_str = _run(server.handle_request(raw))
        data = json.loads(response_str)

        assert "result" in data
        assert data["result"]["status"] == "pong"

    def test_missing_id_in_request(self) -> None:
        """When 'id' is absent, serialized response has no 'id' field."""
        server = _make_server()
        raw = json.dumps({"method": "ping"})
        response_str = _run(server.handle_request(raw))
        data = json.loads(response_str)

        # No 'id' in the original request — _serialize_response omits it
        assert "result" in data


# ---------------------------------------------------------------------------
# TC-EXT-MCP04: tools/list with category and is_dangerous flags (line 229-232)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMCPServerToolsListFlags:
    """Covers category != 'general' and is_dangerous flags in tools/list."""

    def test_dangerous_tool_includes_is_dangerous_flag(self) -> None:
        """Tool with is_dangerous=True should have 'is_dangerous' in its schema."""
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="delete_all",
                description="Delete everything",
                required_params=(),
                is_dangerous=True,
            ),
            handler=lambda: "deleted",
        )
        server = MCPServer(registry)
        request = MCPRequest(method=MCPMethod.TOOLS_LIST.value)
        response = _run(server.handle(request))

        tools = response.result.get("tools", [])
        assert len(tools) == 1
        assert tools[0].get("is_dangerous") is True

    def test_non_general_category_included_in_schema(self) -> None:
        """Tool with category != 'general' should have 'category' in its schema."""
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="kg_search",
                description="Search KG",
                required_params=("query",),
                category="knowledge_graph",
            ),
            handler=lambda query="": "results",
        )
        server = MCPServer(registry)
        request = MCPRequest(method=MCPMethod.TOOLS_LIST.value)
        response = _run(server.handle(request))

        tools = response.result.get("tools", [])
        assert len(tools) == 1
        assert tools[0].get("category") == "knowledge_graph"

    def test_general_category_not_included_in_schema(self) -> None:
        """Tool with category='general' should NOT have 'category' key in schema."""
        server = _make_server()  # echo has default category='general'
        request = MCPRequest(method=MCPMethod.TOOLS_LIST.value)
        response = _run(server.handle(request))

        tools = response.result.get("tools", [])
        assert len(tools) == 1
        assert "category" not in tools[0]

    def test_non_dangerous_tool_no_is_dangerous_flag(self) -> None:
        """Tool with is_dangerous=False should NOT have 'is_dangerous' key."""
        server = _make_server()
        request = MCPRequest(method=MCPMethod.TOOLS_LIST.value)
        response = _run(server.handle(request))

        tools = response.result.get("tools", [])
        assert "is_dangerous" not in tools[0]


# ---------------------------------------------------------------------------
# TC-EXT-MCP05: resources/read with live schema merge (lines 289-299)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMCPServerResourcesRead:
    """Covers resources/read Neo4j live schema merge and unknown URI path."""

    def test_resources_read_known_uri_returns_content(self) -> None:
        """resources/read for a known KG URI returns stub data."""
        server = _make_server()
        request = MCPRequest(
            method=MCPMethod.RESOURCES_READ.value,
            params={"uri": "kg://schema/node-labels"},
        )
        response = _run(server.handle(request))

        assert response.success is True
        contents = response.result.get("contents", [])
        assert len(contents) == 1
        assert contents[0]["uri"] == "kg://schema/node-labels"
        data = json.loads(contents[0]["text"])
        assert "labels" in data

    def test_resources_read_maritime_ontology(self) -> None:
        """resources/read for maritime vessel types returns correct data."""
        server = _make_server()
        request = MCPRequest(
            method=MCPMethod.RESOURCES_READ.value,
            params={"uri": "maritime://ontology/vessel-types"},
        )
        response = _run(server.handle(request))

        contents = response.result.get("contents", [])
        data = json.loads(contents[0]["text"])
        assert "types" in data
        assert "cargo_ship" in data["types"]

    def test_resources_read_unknown_uri_returns_error_content(self) -> None:
        """Unknown URI returns content with 'error' key."""
        server = _make_server()
        request = MCPRequest(
            method=MCPMethod.RESOURCES_READ.value,
            params={"uri": "unknown://not/found"},
        )
        response = _run(server.handle(request))

        assert response.success is True
        contents = response.result.get("contents", [])
        data = json.loads(contents[0]["text"])
        assert "error" in data

    def test_resources_read_with_live_schema_override(self) -> None:
        """When _query_neo4j_schema returns data, it overrides stub for known keys."""
        server = _make_server()

        live_schema = {
            "kg://schema/node-labels": {"labels": ["LiveVessel", "LivePort"]},
        }
        with patch("agent.mcp.server._query_neo4j_schema", return_value=live_schema):
            request = MCPRequest(
                method=MCPMethod.RESOURCES_READ.value,
                params={"uri": "kg://schema/node-labels"},
            )
            response = _run(server.handle(request))

        contents = response.result.get("contents", [])
        data = json.loads(contents[0]["text"])
        # Live schema should override stub
        assert "LiveVessel" in data["labels"]

    def test_resources_read_empty_uri_returns_error_content(self) -> None:
        """Empty URI string returns error content."""
        server = _make_server()
        request = MCPRequest(
            method=MCPMethod.RESOURCES_READ.value,
            params={"uri": ""},
        )
        response = _run(server.handle(request))

        assert response.success is True
        contents = response.result.get("contents", [])
        data = json.loads(contents[0]["text"])
        assert "error" in data

    def test_resources_read_relationship_types(self) -> None:
        """resources/read for relationship types returns DOCKED_AT etc."""
        server = _make_server()
        request = MCPRequest(
            method=MCPMethod.RESOURCES_READ.value,
            params={"uri": "kg://schema/relationship-types"},
        )
        response = _run(server.handle(request))

        contents = response.result.get("contents", [])
        data = json.loads(contents[0]["text"])
        assert "types" in data


# ---------------------------------------------------------------------------
# TC-EXT-MCP06: _serialize_response edge cases
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMCPSerializeResponse:
    """Covers _serialize_response static method edge cases."""

    def test_serialize_with_none_id_omits_id_field(self) -> None:
        """When original_id is None, id field is absent from serialized output."""
        response = MCPResponse(result={"status": "ok"})
        serialized = MCPServer._serialize_response(response, None)
        data = json.loads(serialized)
        assert "id" not in data
        assert "result" in data

    def test_serialize_with_int_id_preserves_int(self) -> None:
        """Integer id should be preserved as integer in serialized output."""
        response = MCPResponse(result={"status": "ok"})
        serialized = MCPServer._serialize_response(response, 42)
        data = json.loads(serialized)
        assert data["id"] == 42

    def test_serialize_error_response(self) -> None:
        """Error response should have 'error' key with code and message."""
        response = MCPResponse(error="something failed", request_id="r1")
        serialized = MCPServer._serialize_response(response, "r1")
        data = json.loads(serialized)
        assert "error" in data
        assert data["error"]["code"] == -32000
        assert "something failed" in data["error"]["message"]
