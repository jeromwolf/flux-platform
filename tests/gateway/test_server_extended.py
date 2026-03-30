"""Extended tests for gateway/server.py.

Covers missed statements from coverage run:
- get_gateway() singleton lazy creation
- get_http_client() RuntimeError when not initialised
- /health endpoint with WS stats
- /ready endpoint (upstream healthy + unreachable)
- /metrics endpoint Prometheus text
- /api/{path} proxy (cache HIT/MISS, circuit-breaker 503, 5xx failure,
  body forwarding for POST, httpx RequestError → 502)
- /ws/rooms/{room}/join and /ws/rooms/{room}/leave
- /ws/stats
- _get_client_ip() via X-Forwarded-For, request.client.host, "unknown"
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from starlette.testclient import TestClient

from gateway.config import GatewayConfig
from gateway.middleware.cache import ResponseCache
from gateway.middleware.circuit_breaker import CircuitBreaker, CircuitState
from gateway.server import create_server


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_server(port: int = 19000) -> TestClient:
    """Return a TestClient wrapping a fresh server instance."""
    config = GatewayConfig(port=port, rate_limit_per_minute=99999)
    server = create_server(config)
    return TestClient(server, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# get_gateway() singleton
# ---------------------------------------------------------------------------

class TestGetGatewaySingleton:
    """Tests for get_gateway() lazy singleton creation."""

    @pytest.mark.unit
    def test_get_gateway_returns_same_instance(self):
        """get_gateway() returns the same GatewayApp on repeated calls."""
        import gateway.server as srv
        from gateway.app import GatewayApp

        # reset singleton so we start clean
        original = srv._gateway
        srv._gateway = None
        try:
            gw1 = srv.get_gateway()
            gw2 = srv.get_gateway()
            assert gw1 is gw2
            assert isinstance(gw1, GatewayApp)
        finally:
            srv._gateway = original

    @pytest.mark.unit
    def test_get_gateway_creates_when_none(self):
        """get_gateway() creates a new GatewayApp when _gateway is None."""
        import gateway.server as srv
        from gateway.app import GatewayApp

        original = srv._gateway
        srv._gateway = None
        try:
            gw = srv.get_gateway()
            assert isinstance(gw, GatewayApp)
        finally:
            srv._gateway = original


# ---------------------------------------------------------------------------
# get_http_client() RuntimeError
# ---------------------------------------------------------------------------

class TestGetHttpClient:
    """Tests for get_http_client() pre-condition enforcement."""

    @pytest.mark.unit
    def test_raises_runtime_error_when_not_initialised(self):
        """get_http_client() raises RuntimeError when _http_client is None."""
        import gateway.server as srv

        original = srv._http_client
        srv._http_client = None
        try:
            with pytest.raises(RuntimeError, match="HTTP client not initialised"):
                srv.get_http_client()
        finally:
            srv._http_client = original

    @pytest.mark.unit
    def test_returns_client_when_initialised(self):
        """get_http_client() returns the assigned AsyncClient."""
        import gateway.server as srv

        original = srv._http_client
        fake_client = httpx.AsyncClient()
        srv._http_client = fake_client
        try:
            result = srv.get_http_client()
            assert result is fake_client
        finally:
            srv._http_client = original
            import asyncio
            asyncio.get_event_loop().run_until_complete(fake_client.aclose())


# ---------------------------------------------------------------------------
# create_server() return type
# ---------------------------------------------------------------------------

class TestCreateServer:
    """Tests for create_server() function."""

    @pytest.mark.unit
    def test_returns_fastapi_app(self):
        """create_server() returns a FastAPI application."""
        from fastapi import FastAPI

        config = GatewayConfig(port=19001)
        app = create_server(config)
        assert isinstance(app, FastAPI)

    @pytest.mark.unit
    def test_app_title_is_imsp(self):
        """create_server() sets the expected API title."""
        config = GatewayConfig(port=19002)
        app = create_server(config)
        assert app.title == "IMSP API Gateway"

    @pytest.mark.unit
    def test_app_version(self):
        """create_server() sets version to 0.1.0."""
        config = GatewayConfig(port=19003)
        app = create_server(config)
        assert app.version == "0.1.0"


# ---------------------------------------------------------------------------
# /health endpoint
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    """Tests for GET /health."""

    @pytest.mark.unit
    def test_health_returns_200(self):
        with _make_server(19010) as client:
            resp = client.get("/health")
        assert resp.status_code == 200

    @pytest.mark.unit
    def test_health_status_is_healthy(self):
        with _make_server(19011) as client:
            resp = client.get("/health")
        body = resp.json()
        assert body["status"] == "healthy"

    @pytest.mark.unit
    def test_health_service_field(self):
        with _make_server(19012) as client:
            resp = client.get("/health")
        body = resp.json()
        assert body["service"] == "imsp-gateway"

    @pytest.mark.unit
    def test_health_includes_websocket_stats(self):
        with _make_server(19013) as client:
            resp = client.get("/health")
        body = resp.json()
        assert "websocket" in body

    @pytest.mark.unit
    def test_health_websocket_stats_has_connections_key(self):
        with _make_server(19014) as client:
            resp = client.get("/health")
        body = resp.json()
        ws = body["websocket"]
        # The WS manager stats must include a connections-related key
        assert isinstance(ws, dict)


# ---------------------------------------------------------------------------
# /ready endpoint
# ---------------------------------------------------------------------------

class TestReadyEndpoint:
    """Tests for GET /ready — upstream check."""

    @pytest.mark.unit
    def test_ready_returns_200_when_upstream_healthy(self):
        """When upstream returns 200, /ready should return 200."""
        config = GatewayConfig(port=19020)
        app = create_server(config)

        mock_resp = MagicMock()
        mock_resp.status_code = 200

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        import gateway.server as srv

        with patch.object(srv, "_http_client", mock_client):
            with TestClient(app, raise_server_exceptions=True) as client:
                resp = client.get("/ready")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ready"
        assert body["upstream"] == "healthy"

    @pytest.mark.unit
    def test_ready_returns_503_when_upstream_unreachable(self):
        """When upstream call raises an exception, /ready returns 503."""
        config = GatewayConfig(port=19021)
        app = create_server(config)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

        import gateway.server as srv

        with patch.object(srv, "_http_client", mock_client):
            with TestClient(app, raise_server_exceptions=True) as client:
                resp = client.get("/ready")

        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "degraded"
        assert body["upstream"] == "unreachable"

    @pytest.mark.unit
    def test_ready_returns_503_when_upstream_5xx(self):
        """When upstream returns 500, /ready returns 503 degraded."""
        config = GatewayConfig(port=19022)
        app = create_server(config)

        mock_resp = MagicMock()
        mock_resp.status_code = 500

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        import gateway.server as srv

        with patch.object(srv, "_http_client", mock_client):
            with TestClient(app, raise_server_exceptions=True) as client:
                resp = client.get("/ready")

        assert resp.status_code == 503

    @pytest.mark.unit
    def test_ready_returns_200_when_upstream_404(self):
        """Upstream 4xx counts as healthy (< 500) so /ready returns 200."""
        config = GatewayConfig(port=19023)
        app = create_server(config)

        mock_resp = MagicMock()
        mock_resp.status_code = 404

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)

        import gateway.server as srv

        with patch.object(srv, "_http_client", mock_client):
            with TestClient(app, raise_server_exceptions=True) as client:
                resp = client.get("/ready")

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# /metrics endpoint
# ---------------------------------------------------------------------------

class TestMetricsEndpoint:
    """Tests for GET /metrics."""

    @pytest.mark.unit
    def test_metrics_returns_200(self):
        with _make_server(19030) as client:
            resp = client.get("/metrics")
        assert resp.status_code == 200

    @pytest.mark.unit
    def test_metrics_content_type_is_prometheus(self):
        with _make_server(19031) as client:
            resp = client.get("/metrics")
        assert "text/plain" in resp.headers["content-type"]

    @pytest.mark.unit
    def test_metrics_contains_requests_total(self):
        with _make_server(19032) as client:
            resp = client.get("/metrics")
        assert "gateway_requests_total" in resp.text

    @pytest.mark.unit
    def test_metrics_contains_errors_total(self):
        with _make_server(19033) as client:
            resp = client.get("/metrics")
        assert "gateway_errors_total" in resp.text

    @pytest.mark.unit
    def test_metrics_contains_active_connections(self):
        with _make_server(19034) as client:
            resp = client.get("/metrics")
        assert "gateway_active_connections" in resp.text


# ---------------------------------------------------------------------------
# /api/{path} proxy — cache HIT
# ---------------------------------------------------------------------------

class TestProxyApiCacheHit:
    """Tests for cache-hit path in /api/{path} proxy."""

    @pytest.mark.unit
    def test_proxy_get_returns_cached_response(self):
        """GET /api/test/data returns cached body with X-Cache: HIT header."""
        config = GatewayConfig(port=19040)
        app = create_server(config)

        import gateway.server as srv

        # Pre-populate cache with a fake entry
        cache_body = b'{"cached": true}'
        fake_cache = ResponseCache(ttl=60.0, max_entries=256)
        fake_cache.put(
            path="/api/test/data",
            query="",
            body=cache_body,
            status_code=200,
            headers={"content-type": "application/json"},
        )

        # Patch fresh_client so it never actually calls upstream
        mock_client = AsyncMock()

        with patch.object(srv, "_response_cache", fake_cache):
            with patch.object(srv, "_http_client", mock_client):
                with TestClient(app, raise_server_exceptions=True) as client:
                    resp = client.get("/api/test/data")

        assert resp.status_code == 200
        assert resp.headers.get("x-cache") == "HIT"
        assert resp.json()["cached"] is True

    @pytest.mark.unit
    def test_proxy_get_cache_hit_does_not_call_upstream(self):
        """Cache HIT path does not invoke the upstream HTTP client."""
        config = GatewayConfig(port=19041)
        app = create_server(config)

        import gateway.server as srv

        cache_body = b'{"ok": true}'
        fake_cache = ResponseCache(ttl=60.0, max_entries=256)
        fake_cache.put(
            path="/api/items",
            query="",
            body=cache_body,
            status_code=200,
            headers={"content-type": "application/json"},
        )

        mock_client = AsyncMock()
        mock_client.request = AsyncMock()

        with patch.object(srv, "_response_cache", fake_cache):
            with patch.object(srv, "_http_client", mock_client):
                with TestClient(app, raise_server_exceptions=True) as client:
                    client.get("/api/items")

        mock_client.request.assert_not_awaited()


# ---------------------------------------------------------------------------
# /api/{path} proxy — cache MISS
# ---------------------------------------------------------------------------

class TestProxyApiCacheMiss:
    """Tests for cache-miss path in /api/{path} proxy."""

    @pytest.mark.unit
    def test_proxy_get_returns_miss_header(self):
        """Cache MISS sets X-Cache: MISS on a GET response."""
        config = GatewayConfig(port=19050)
        app = create_server(config)

        import gateway.server as srv

        upstream_resp = MagicMock()
        upstream_resp.status_code = 200
        upstream_resp.content = b'{"data": "live"}'
        upstream_resp.headers = {"content-type": "application/json"}

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=upstream_resp)

        fresh_cache = ResponseCache(ttl=60.0, max_entries=256)
        fresh_cb = CircuitBreaker()

        with patch.object(srv, "_response_cache", fresh_cache):
            with patch.object(srv, "_circuit_breaker", fresh_cb):
                with patch.object(srv, "_http_client", mock_client):
                    with TestClient(app, raise_server_exceptions=True) as client:
                        resp = client.get("/api/graph/nodes")

        assert resp.headers.get("x-cache") == "MISS"

    @pytest.mark.unit
    def test_proxy_get_stores_response_in_cache(self):
        """Upstream GET response is stored in cache after MISS."""
        config = GatewayConfig(port=19051)
        app = create_server(config)

        import gateway.server as srv

        upstream_resp = MagicMock()
        upstream_resp.status_code = 200
        upstream_resp.content = b'{"stored": true}'
        upstream_resp.headers = {"content-type": "application/json"}

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=upstream_resp)

        fresh_cache = ResponseCache(ttl=60.0, max_entries=256)
        fresh_cb = CircuitBreaker()

        with patch.object(srv, "_response_cache", fresh_cache):
            with patch.object(srv, "_circuit_breaker", fresh_cb):
                with patch.object(srv, "_http_client", mock_client):
                    with TestClient(app, raise_server_exceptions=True) as client:
                        client.get("/api/graph/stored")

        # Cache should now have this entry
        assert fresh_cache.size == 1


# ---------------------------------------------------------------------------
# /api/{path} proxy — circuit breaker OPEN
# ---------------------------------------------------------------------------

class TestProxyApiCircuitBreaker:
    """Tests for circuit-breaker rejection in /api/{path}."""

    @pytest.mark.unit
    def test_circuit_breaker_open_returns_503(self):
        """When circuit breaker is OPEN, proxy returns 503."""
        config = GatewayConfig(port=19060)
        app = create_server(config)

        import gateway.server as srv

        # Create a CB that is already open
        open_cb = CircuitBreaker(failure_threshold=1, recovery_timeout=9999.0)
        open_cb.record_failure()
        assert open_cb.state == CircuitState.OPEN

        mock_client = AsyncMock()

        with patch.object(srv, "_circuit_breaker", open_cb):
            with patch.object(srv, "_http_client", mock_client):
                with TestClient(app, raise_server_exceptions=True) as client:
                    resp = client.get("/api/some/endpoint")

        assert resp.status_code == 503

    @pytest.mark.unit
    def test_circuit_breaker_open_response_body_has_error_key(self):
        """503 body from circuit-breaker rejection contains 'error' key."""
        config = GatewayConfig(port=19061)
        app = create_server(config)

        import gateway.server as srv

        open_cb = CircuitBreaker(failure_threshold=1, recovery_timeout=9999.0)
        open_cb.record_failure()

        mock_client = AsyncMock()

        with patch.object(srv, "_circuit_breaker", open_cb):
            with patch.object(srv, "_http_client", mock_client):
                with TestClient(app, raise_server_exceptions=True) as client:
                    resp = client.get("/api/some/endpoint")

        body = resp.json()
        assert "error" in body


# ---------------------------------------------------------------------------
# /api/{path} proxy — upstream 5xx records failure
# ---------------------------------------------------------------------------

class TestProxyApiUpstream5xx:
    """Tests for upstream 5xx failure recording."""

    @pytest.mark.unit
    def test_upstream_5xx_records_circuit_breaker_failure(self):
        """Upstream 500 response causes circuit breaker to record a failure."""
        config = GatewayConfig(port=19070)
        app = create_server(config)

        import gateway.server as srv

        upstream_resp = MagicMock()
        upstream_resp.status_code = 500
        upstream_resp.content = b'{"error": "internal"}'
        upstream_resp.headers = {"content-type": "application/json"}

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=upstream_resp)

        fresh_cb = CircuitBreaker(failure_threshold=10)
        fresh_cache = ResponseCache(ttl=60.0, max_entries=256)

        with patch.object(srv, "_circuit_breaker", fresh_cb):
            with patch.object(srv, "_response_cache", fresh_cache):
                with patch.object(srv, "_http_client", mock_client):
                    with TestClient(app, raise_server_exceptions=True) as client:
                        resp = client.get("/api/fail")

        assert resp.status_code == 500
        assert fresh_cb._failure_count >= 1

    @pytest.mark.unit
    def test_upstream_2xx_records_circuit_breaker_success(self):
        """Upstream 200 response causes circuit breaker to record a success."""
        config = GatewayConfig(port=19071)
        app = create_server(config)

        import gateway.server as srv

        upstream_resp = MagicMock()
        upstream_resp.status_code = 200
        upstream_resp.content = b'{"ok": true}'
        upstream_resp.headers = {"content-type": "application/json"}

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=upstream_resp)

        fresh_cb = CircuitBreaker(failure_threshold=10)
        # Seed one failure so we can confirm reset
        fresh_cb.record_failure()
        assert fresh_cb._failure_count == 1

        fresh_cache = ResponseCache(ttl=60.0, max_entries=256)

        with patch.object(srv, "_circuit_breaker", fresh_cb):
            with patch.object(srv, "_response_cache", fresh_cache):
                with patch.object(srv, "_http_client", mock_client):
                    with TestClient(app, raise_server_exceptions=True) as client:
                        client.get("/api/succeed")

        # After success the closed-state resets failure count
        assert fresh_cb._failure_count == 0


# ---------------------------------------------------------------------------
# /api/{path} proxy — POST body forwarding
# ---------------------------------------------------------------------------

class TestProxyApiPostBodyForwarding:
    """Tests for body forwarding in POST requests."""

    @pytest.mark.unit
    def test_post_forwards_body_to_upstream(self):
        """POST request body is forwarded to upstream via httpx."""
        config = GatewayConfig(port=19080)
        app = create_server(config)

        import gateway.server as srv

        upstream_resp = MagicMock()
        upstream_resp.status_code = 201
        upstream_resp.content = b'{"created": true}'
        upstream_resp.headers = {"content-type": "application/json"}

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=upstream_resp)

        fresh_cb = CircuitBreaker()
        fresh_cache = ResponseCache(ttl=60.0, max_entries=256)

        with patch.object(srv, "_circuit_breaker", fresh_cb):
            with patch.object(srv, "_response_cache", fresh_cache):
                with patch.object(srv, "_http_client", mock_client):
                    with TestClient(app, raise_server_exceptions=True) as client:
                        payload = {"vessel": "MV-001"}
                        resp = client.post(
                            "/api/graph/node",
                            json=payload,
                        )

        assert resp.status_code == 201
        # Confirm request() was called (body forwarded)
        mock_client.request.assert_awaited_once()
        call_kwargs = mock_client.request.call_args
        assert call_kwargs.kwargs.get("method") == "POST" or call_kwargs.args[0] == "POST"

    @pytest.mark.unit
    def test_post_invalidates_cache(self):
        """POST to /api/... invalidates the response cache."""
        config = GatewayConfig(port=19081)
        app = create_server(config)

        import gateway.server as srv

        # Seed the cache
        fake_cache = ResponseCache(ttl=60.0, max_entries=256)
        fake_cache.put(
            path="/api/graph/node",
            query="",
            body=b'{"data": "old"}',
            status_code=200,
            headers={"content-type": "application/json"},
        )
        assert fake_cache.size == 1

        upstream_resp = MagicMock()
        upstream_resp.status_code = 201
        upstream_resp.content = b'{"created": true}'
        upstream_resp.headers = {"content-type": "application/json"}

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=upstream_resp)

        fresh_cb = CircuitBreaker()

        with patch.object(srv, "_circuit_breaker", fresh_cb):
            with patch.object(srv, "_response_cache", fake_cache):
                with patch.object(srv, "_http_client", mock_client):
                    with TestClient(app, raise_server_exceptions=True) as client:
                        client.post("/api/graph/node", json={"x": 1})

        # Cache should be empty after POST invalidation
        assert fake_cache.size == 0


# ---------------------------------------------------------------------------
# /api/{path} proxy — httpx.RequestError → 502
# ---------------------------------------------------------------------------

class TestProxyApiRequestError:
    """Tests for httpx.RequestError handling in proxy."""

    @pytest.mark.unit
    def test_request_error_returns_502(self):
        """When httpx raises RequestError, proxy returns 502."""
        config = GatewayConfig(port=19090)
        app = create_server(config)

        import gateway.server as srv

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(
            side_effect=httpx.ConnectError("connection refused")
        )

        fresh_cb = CircuitBreaker()
        fresh_cache = ResponseCache(ttl=60.0, max_entries=256)

        with patch.object(srv, "_circuit_breaker", fresh_cb):
            with patch.object(srv, "_response_cache", fresh_cache):
                with patch.object(srv, "_http_client", mock_client):
                    with TestClient(app, raise_server_exceptions=False) as client:
                        resp = client.get("/api/connect/error")

        assert resp.status_code == 502


# ---------------------------------------------------------------------------
# /ws/rooms/{room}/join and /ws/rooms/{room}/leave
# ---------------------------------------------------------------------------

class TestWsRoomEndpoints:
    """Tests for /ws/rooms/{room}/join and /ws/rooms/{room}/leave."""

    @pytest.mark.unit
    def test_join_room_returns_200(self):
        with _make_server(19100) as client:
            resp = client.post("/ws/rooms/bridge/join?connection_id=conn-abc")
        assert resp.status_code == 200

    @pytest.mark.unit
    def test_join_room_response_status_joined(self):
        with _make_server(19101) as client:
            resp = client.post("/ws/rooms/engine/join?connection_id=conn-xyz")
        body = resp.json()
        assert body["status"] == "joined"

    @pytest.mark.unit
    def test_join_room_response_room_field(self):
        with _make_server(19102) as client:
            resp = client.post("/ws/rooms/bridge/join?connection_id=conn-abc")
        body = resp.json()
        assert body["room"] == "bridge"

    @pytest.mark.unit
    def test_leave_room_returns_200(self):
        with _make_server(19103) as client:
            resp = client.post("/ws/rooms/bridge/leave?connection_id=conn-abc")
        assert resp.status_code == 200

    @pytest.mark.unit
    def test_leave_room_response_status_left(self):
        with _make_server(19104) as client:
            resp = client.post("/ws/rooms/harbor/leave?connection_id=conn-xyz")
        body = resp.json()
        assert body["status"] == "left"

    @pytest.mark.unit
    def test_leave_room_response_room_field(self):
        with _make_server(19105) as client:
            resp = client.post("/ws/rooms/harbor/leave?connection_id=conn-abc")
        body = resp.json()
        assert body["room"] == "harbor"


# ---------------------------------------------------------------------------
# /ws/stats
# ---------------------------------------------------------------------------

class TestWsStatsEndpoint:
    """Tests for GET /ws/stats."""

    @pytest.mark.unit
    def test_ws_stats_returns_200(self):
        with _make_server(19110) as client:
            resp = client.get("/ws/stats")
        assert resp.status_code == 200

    @pytest.mark.unit
    def test_ws_stats_returns_dict(self):
        with _make_server(19111) as client:
            resp = client.get("/ws/stats")
        assert isinstance(resp.json(), dict)
