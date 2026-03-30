"""Tests for gateway/routes/proxy.py.

Covers missed statements from coverage run:
- ProxyRoute dataclass construction and field defaults
- APIProxy.base_url property
- APIProxy.get_routes() contents
- APIProxy._match_route() — no match ValueError, method not allowed ValueError
- APIProxy.forward_request() — success, HTTPError, URLError → RuntimeError
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from gateway.routes.proxy import APIProxy, ProxyRoute


# ---------------------------------------------------------------------------
# ProxyRoute — dataclass construction
# ---------------------------------------------------------------------------

class TestProxyRouteDefaults:
    """Tests for ProxyRoute default field values."""

    @pytest.mark.unit
    def test_default_methods_is_get_only(self):
        """Default methods tuple contains only GET."""
        r = ProxyRoute(path="/test", target_url="http://localhost/test")
        assert r.methods == ("GET",)

    @pytest.mark.unit
    def test_default_require_auth_is_true(self):
        """Default require_auth is True."""
        r = ProxyRoute(path="/test", target_url="http://localhost/test")
        assert r.require_auth is True

    @pytest.mark.unit
    def test_default_timeout_is_30(self):
        """Default timeout is 30.0 seconds."""
        r = ProxyRoute(path="/test", target_url="http://localhost/test")
        assert r.timeout == 30.0

    @pytest.mark.unit
    def test_custom_fields_stored_correctly(self):
        """Custom fields are stored as provided."""
        r = ProxyRoute(
            path="/query",
            target_url="http://backend/query",
            methods=("GET", "POST"),
            require_auth=False,
            timeout=60.0,
        )
        assert r.path == "/query"
        assert r.target_url == "http://backend/query"
        assert r.methods == ("GET", "POST")
        assert r.require_auth is False
        assert r.timeout == 60.0

    @pytest.mark.unit
    def test_frozen_dataclass_is_immutable(self):
        """ProxyRoute is frozen — mutation raises FrozenInstanceError."""
        r = ProxyRoute(path="/test", target_url="http://localhost/test")
        with pytest.raises((AttributeError, TypeError)):
            r.path = "/new"  # type: ignore[misc]

    @pytest.mark.unit
    def test_equality_same_fields(self):
        """Two ProxyRoutes with identical fields are equal."""
        r1 = ProxyRoute(path="/test", target_url="http://localhost/test")
        r2 = ProxyRoute(path="/test", target_url="http://localhost/test")
        assert r1 == r2

    @pytest.mark.unit
    def test_hashable_in_set(self):
        """ProxyRoute (frozen) is hashable and usable in a set."""
        r1 = ProxyRoute(path="/a", target_url="http://h/a")
        r2 = ProxyRoute(path="/a", target_url="http://h/a")
        r3 = ProxyRoute(path="/b", target_url="http://h/b")
        s = {r1, r2, r3}
        assert len(s) == 2


# ---------------------------------------------------------------------------
# APIProxy — construction and base_url
# ---------------------------------------------------------------------------

class TestAPIProxyConstruction:
    """Tests for APIProxy constructor and base_url property."""

    @pytest.mark.unit
    def test_base_url_default(self):
        """Default base_url is http://localhost:8000."""
        proxy = APIProxy()
        assert proxy.base_url == "http://localhost:8000"

    @pytest.mark.unit
    def test_base_url_trailing_slash_stripped(self):
        """Trailing slash is stripped from base_url."""
        proxy = APIProxy(base_url="http://localhost:8000/")
        assert proxy.base_url == "http://localhost:8000"

    @pytest.mark.unit
    def test_base_url_custom(self):
        """Custom base_url is stored correctly."""
        proxy = APIProxy(base_url="http://core-api:9000")
        assert proxy.base_url == "http://core-api:9000"

    @pytest.mark.unit
    def test_base_url_property_returns_string(self):
        """base_url property always returns a str."""
        proxy = APIProxy(base_url="http://test:1234")
        assert isinstance(proxy.base_url, str)


# ---------------------------------------------------------------------------
# APIProxy.get_routes()
# ---------------------------------------------------------------------------

class TestGetRoutes:
    """Tests for APIProxy.get_routes()."""

    @pytest.mark.unit
    def test_returns_list(self):
        """get_routes() returns a list."""
        proxy = APIProxy()
        routes = proxy.get_routes()
        assert isinstance(routes, list)

    @pytest.mark.unit
    def test_all_elements_are_proxy_routes(self):
        """All elements in get_routes() are ProxyRoute instances."""
        proxy = APIProxy()
        for r in proxy.get_routes():
            assert isinstance(r, ProxyRoute)

    @pytest.mark.unit
    def test_health_route_present(self):
        """/health route is in get_routes()."""
        proxy = APIProxy()
        paths = [r.path for r in proxy.get_routes()]
        assert "/health" in paths

    @pytest.mark.unit
    def test_health_route_require_auth_false(self):
        """/health route has require_auth=False."""
        proxy = APIProxy()
        health = next(r for r in proxy.get_routes() if r.path == "/health")
        assert health.require_auth is False

    @pytest.mark.unit
    def test_ready_route_require_auth_false(self):
        """/ready route has require_auth=False."""
        proxy = APIProxy()
        ready = next(r for r in proxy.get_routes() if r.path == "/ready")
        assert ready.require_auth is False

    @pytest.mark.unit
    def test_graph_query_route_present(self):
        """/graph/query route is in get_routes()."""
        proxy = APIProxy()
        paths = [r.path for r in proxy.get_routes()]
        assert "/graph/query" in paths

    @pytest.mark.unit
    def test_rag_query_route_present(self):
        """/rag/query route is in get_routes()."""
        proxy = APIProxy()
        paths = [r.path for r in proxy.get_routes()]
        assert "/rag/query" in paths

    @pytest.mark.unit
    def test_agent_chat_route_present(self):
        """/agent/chat route is in get_routes()."""
        proxy = APIProxy()
        paths = [r.path for r in proxy.get_routes()]
        assert "/agent/chat" in paths

    @pytest.mark.unit
    def test_no_duplicate_paths(self):
        """get_routes() returns no duplicate path entries."""
        proxy = APIProxy()
        paths = [r.path for r in proxy.get_routes()]
        assert len(paths) == len(set(paths))

    @pytest.mark.unit
    def test_target_urls_include_base_url(self):
        """All target_urls start with the configured base_url."""
        proxy = APIProxy(base_url="http://core:9090")
        for r in proxy.get_routes():
            assert r.target_url.startswith("http://core:9090"), (
                f"Route {r.path} target_url does not start with base_url"
            )

    @pytest.mark.unit
    def test_all_paths_start_with_slash(self):
        """All route paths start with '/'."""
        proxy = APIProxy()
        for r in proxy.get_routes():
            assert r.path.startswith("/"), f"Path '{r.path}' missing leading slash"

    @pytest.mark.unit
    def test_mcp_route_present(self):
        """/mcp route is in get_routes()."""
        proxy = APIProxy()
        paths = [r.path for r in proxy.get_routes()]
        assert "/mcp" in paths

    @pytest.mark.unit
    def test_fresh_list_each_call(self):
        """get_routes() returns a fresh list on each call."""
        proxy = APIProxy()
        assert proxy.get_routes() is not proxy.get_routes()


# ---------------------------------------------------------------------------
# APIProxy._match_route()
# ---------------------------------------------------------------------------

class TestMatchRoute:
    """Tests for APIProxy._match_route()."""

    @pytest.mark.unit
    def test_match_existing_route(self):
        """_match_route() returns the matching ProxyRoute."""
        proxy = APIProxy()
        route = proxy._match_route("/health", "GET")
        assert route.path == "/health"

    @pytest.mark.unit
    def test_match_trailing_slash_normalised(self):
        """Trailing slash is stripped when matching."""
        proxy = APIProxy()
        route = proxy._match_route("/health/", "GET")
        assert route.path == "/health"

    @pytest.mark.unit
    def test_no_match_raises_value_error(self):
        """_match_route() raises ValueError for unknown path."""
        proxy = APIProxy()
        with pytest.raises(ValueError, match="No proxy route configured"):
            proxy._match_route("/nonexistent/path", "GET")

    @pytest.mark.unit
    def test_method_not_allowed_raises_value_error(self):
        """_match_route() raises ValueError when method is disallowed."""
        proxy = APIProxy()
        # /health only allows GET
        with pytest.raises(ValueError, match="not allowed"):
            proxy._match_route("/health", "DELETE")

    @pytest.mark.unit
    def test_method_case_insensitive(self):
        """_match_route() treats method case-insensitively."""
        proxy = APIProxy()
        # /graph/query allows GET
        route = proxy._match_route("/graph/query", "get")
        assert route.path == "/graph/query"


# ---------------------------------------------------------------------------
# APIProxy.forward_request()
# ---------------------------------------------------------------------------

class TestForwardRequest:
    """Tests for APIProxy.forward_request()."""

    @pytest.mark.unit
    def test_forward_request_no_route_raises(self):
        """forward_request() raises ValueError for unknown path."""
        import asyncio
        proxy = APIProxy()

        async def _run():
            return await proxy.forward_request("GET", "/no-such-path", {})

        with pytest.raises(ValueError, match="No proxy route"):
            asyncio.get_event_loop().run_until_complete(_run())

    @pytest.mark.unit
    def test_forward_request_method_not_allowed_raises(self):
        """forward_request() raises ValueError for disallowed method."""
        import asyncio
        proxy = APIProxy()

        async def _run():
            return await proxy.forward_request("DELETE", "/health", {})

        with pytest.raises(ValueError, match="not allowed"):
            asyncio.get_event_loop().run_until_complete(_run())

    @pytest.mark.unit
    def test_forward_request_http_error_returns_status(self):
        """HTTPError from urllib is returned as status dict."""
        import asyncio
        proxy = APIProxy()

        fp_mock = BytesIO(b'{"error": "not found"}')
        http_err = urllib.error.HTTPError(
            url="http://localhost:8000/health",
            code=404,
            msg="Not Found",
            hdrs=MagicMock(items=lambda: [("content-type", "application/json")]),
            fp=fp_mock,
        )

        with patch("urllib.request.urlopen", side_effect=http_err):
            async def _run():
                return await proxy.forward_request("GET", "/health", {})

            result = asyncio.get_event_loop().run_until_complete(_run())

        assert result["status_code"] == 404
        assert "not found" in result["body"]

    @pytest.mark.unit
    def test_forward_request_url_error_raises_runtime(self):
        """URLError from urllib raises RuntimeError with descriptive message."""
        import asyncio
        proxy = APIProxy()

        url_err = urllib.error.URLError(reason="Connection refused")

        with patch("urllib.request.urlopen", side_effect=url_err):
            async def _run():
                return await proxy.forward_request("GET", "/health", {})

            with pytest.raises(RuntimeError, match="Upstream service unreachable"):
                asyncio.get_event_loop().run_until_complete(_run())

    @pytest.mark.unit
    def test_forward_request_success_full_response(self):
        """forward_request() returns a complete response dict on 200."""
        import asyncio
        proxy = APIProxy()

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"status": "ok"}'
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            async def _run():
                return await proxy.forward_request("GET", "/health", {"Accept": "application/json"})

            result = asyncio.get_event_loop().run_until_complete(_run())

        assert result["status_code"] == 200
        assert "ok" in result["body"]
        assert isinstance(result["headers"], dict)
