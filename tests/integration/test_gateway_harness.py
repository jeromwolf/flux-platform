"""Gateway → Core API harness integration tests.

Tests the Gateway proxy behavior by wiring both the Gateway and Core API
as ASGI apps connected via httpx.ASGITransport — no TCP ports needed.

Architecture:
    [Test Client] → [Gateway ASGI] → [httpx + ASGITransport] → [Core API ASGI]
                                              ↑
                                       (mocked Neo4j session)
"""
from __future__ import annotations

import pytest
import pytest_asyncio
import httpx
from httpx import ASGITransport
from unittest.mock import patch

from tests.helpers.mock_neo4j import (
    MockNeo4jSession,
    MockNeo4jResult,
    make_neo4j_node,
    build_node_record,
    count_record,
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.asyncio,
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def gateway_client():
    """Gateway test client with Core API as mock ASGI backend.

    Wires:
        1. Core API (FastAPI) with MockNeo4jSession injected
        2. httpx.AsyncClient pointing at Core API via ASGITransport
        3. Gateway app whose get_http_client() returns the ASGI client
        4. httpx.AsyncClient pointing at Gateway via ASGITransport

    Yields:
        Tuple of (gateway_http_client, mock_neo4j_session)
    """
    from kg.config import AppConfig, Neo4jConfig, reset, set_config
    from kg.api.app import create_app
    from kg.api.deps import get_async_neo4j_session
    from gateway.config import GatewayConfig
    from gateway.server import create_server
    import gateway.server as gw_server

    # 1. Create Core API with development config so auth is bypassed
    core_config = AppConfig(env="development", neo4j=Neo4jConfig(uri="bolt://mock:7687"))
    set_config(core_config)

    with patch("kg.api.app.get_config", return_value=core_config), \
         patch("kg.api.app.set_config"):
        core_app = create_app(config=core_config)

    # 2. Create a shared mock session and override the dependency
    session = MockNeo4jSession()

    async def _override_session():
        yield session

    core_app.dependency_overrides[get_async_neo4j_session] = _override_session

    # 3. Create an httpx.AsyncClient pointing at Core API via ASGI transport
    core_transport = ASGITransport(app=core_app)
    core_http_client = httpx.AsyncClient(
        transport=core_transport,
        base_url="http://core-api",
    )

    # 4. Create Gateway app with api_base_url matching core_http_client base_url
    gw_config = GatewayConfig(
        port=8080,
        api_base_url="http://core-api",
    )

    # Create the gateway server — this sets _gateway but NOT _http_client
    # (lifespan handles _http_client, but we inject our ASGI client instead)
    gw_app = create_server(gw_config)

    # Inject our ASGI-backed client into the module globals so get_http_client()
    # returns it and proxy_api() uses it instead of the real TCP client
    gw_server._http_client = core_http_client

    # Also reset circuit breaker and cache so tests are isolated
    gw_server._circuit_breaker.reset()
    gw_server._response_cache.invalidate()

    # 5. Create test client for Gateway via ASGITransport (no TCP needed)
    gw_transport = ASGITransport(app=gw_app)
    async with httpx.AsyncClient(transport=gw_transport, base_url="http://gateway") as client:
        yield client, session

    # Cleanup
    await core_http_client.aclose()
    # Reset module-level state
    gw_server._http_client = None
    gw_server._circuit_breaker.reset()
    gw_server._response_cache.invalidate()
    reset()


# ---------------------------------------------------------------------------
# TestGatewayHealth
# ---------------------------------------------------------------------------


class TestGatewayHealth:
    """Tests for the Gateway's own health endpoints."""

    async def test_gateway_health(self, gateway_client):
        """GET /health returns gateway health status."""
        client, _ = gateway_client
        resp = await client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["service"] == "imsp-gateway"

    async def test_gateway_readiness(self, gateway_client):
        """GET /ready checks upstream Core API health via proxy.

        The readiness endpoint calls GET /api/v1/health on the upstream.
        We pre-load the mock session with the Neo4j ping result.
        """
        client, session = gateway_client
        # The health route runs: RETURN 1 AS n
        session._side_effects = [MockNeo4jResult([{"n": 1}])]
        session._call_index = 0
        resp = await client.get("/ready")
        assert resp.status_code == 200
        body = resp.json()
        assert body["upstream"] == "healthy"


# ---------------------------------------------------------------------------
# TestGatewayProxy
# ---------------------------------------------------------------------------


class TestGatewayProxy:
    """Tests for the Gateway's /api/* proxy behavior."""

    async def test_proxy_health_endpoint(self, gateway_client):
        """GET /api/v1/health proxied to Core API returns ok status."""
        client, session = gateway_client
        # Core API health checks Neo4j with RETURN 1 AS n
        session._side_effects = [MockNeo4jResult([{"n": 1}])]
        session._call_index = 0
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"

    async def test_proxy_list_nodes(self, gateway_client):
        """GET /api/v1/nodes proxied to Core API returns node list."""
        client, session = gateway_client
        # list_nodes runs: count query + list query
        node = make_neo4j_node(
            element_id="4:test:1",
            labels=["Vessel"],
            props={"name": "테스트함"},
        )
        session._side_effects = [
            MockNeo4jResult([count_record(1)]),          # COUNT query
            MockNeo4jResult([build_node_record(node)]),  # list query
        ]
        session._call_index = 0

        resp = await client.get("/api/v1/nodes", params={"limit": 10})
        assert resp.status_code == 200
        body = resp.json()
        assert "nodes" in body
        assert "total" in body
        assert body["total"] == 1
        assert len(body["nodes"]) == 1

    async def test_proxy_dangerous_cypher_blocked(self, gateway_client):
        """POST /api/v1/cypher/execute with DROP keyword returns 403."""
        client, _ = gateway_client
        resp = await client.post(
            "/api/v1/cypher/execute",
            json={"cypher": "DROP INDEX my_index"},
        )
        # Core API blocks DROP at the Cypher validation layer (403)
        assert resp.status_code == 403

    async def test_proxy_circuit_breaker_state(self, gateway_client):
        """Circuit breaker starts in CLOSED state (allow_request returns True)."""
        import gateway.server as gw_server
        from gateway.middleware.circuit_breaker import CircuitState

        # After fixture setup, circuit breaker should be freshly reset (CLOSED)
        assert gw_server._circuit_breaker.state == CircuitState.CLOSED
        assert gw_server._circuit_breaker.allow_request() is True

    async def test_response_cache_miss_then_hit(self, gateway_client):
        """Second GET /api/v1/nodes returns cached response (X-Cache: HIT).

        The Gateway caches GET responses for non-skip paths. /api/v1/nodes
        is cacheable (not in CACHE_SKIP_PATHS = /health, /ready, /metrics).
        Note: skip_cache uses substring matching, so /api/v1/health is also
        skipped (contains '/health'). Using /api/v1/nodes avoids this.
        """
        import gateway.server as gw_server

        client, session = gateway_client

        # Invalidate cache to ensure clean state
        gw_server._response_cache.invalidate()

        node = make_neo4j_node(
            element_id="4:cache:1",
            labels=["Vessel"],
            props={"name": "캐시테스트"},
        )

        # Prime with two sets of count+list results (only first will be used
        # if caching works correctly)
        session._side_effects = [
            MockNeo4jResult([count_record(1)]),          # First request: COUNT
            MockNeo4jResult([build_node_record(node)]),  # First request: LIST
            MockNeo4jResult([count_record(1)]),          # Second request (if cache miss)
            MockNeo4jResult([build_node_record(node)]),  # Second request (if cache miss)
        ]
        session._call_index = 0

        # First request — cache MISS (X-Cache: MISS header expected)
        resp1 = await client.get("/api/v1/nodes", params={"limit": 5})
        assert resp1.status_code == 200
        assert resp1.headers.get("x-cache") == "MISS"

        # Second identical request — should be served from cache
        calls_before = session._call_index
        resp2 = await client.get("/api/v1/nodes", params={"limit": 5})
        assert resp2.status_code == 200
        # Cache hit — session should NOT have been called again
        assert session._call_index == calls_before
        assert resp2.headers.get("x-cache") == "HIT"
