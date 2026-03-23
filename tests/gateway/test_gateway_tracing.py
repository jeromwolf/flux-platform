"""Tests for GatewayTracingMiddleware — W3C Traceparent propagation + Zipkin export.

TC-GT01: Middleware generates a traceparent header when none is incoming.
TC-GT02: Middleware propagates an existing trace_id from an incoming traceparent.
TC-GT03: _report_span fires to Zipkin endpoint (mocked urlopen).
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from starlette.requests import Request
from starlette.testclient import TestClient

from gateway.middleware.tracing import GatewayTracingMiddleware, _report_span


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tracing_app() -> FastAPI:
    """Return a minimal FastAPI app with GatewayTracingMiddleware installed."""
    app = FastAPI()
    app.add_middleware(GatewayTracingMiddleware)

    @app.get("/ping")
    async def _ping(request: Request):
        return {
            "trace_id": getattr(request.state, "trace_id", None),
            "span_id": getattr(request.state, "span_id", None),
        }

    return app


# ---------------------------------------------------------------------------
# TC-GT01: Middleware generates traceparent when no header is present
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTracingMiddlewareGenerates:
    def test_tracing_middleware_generates_traceparent(self) -> None:
        """TC-GT01: Response carries a valid W3C traceparent header for cold requests."""
        app = _make_tracing_app()
        client = TestClient(app, raise_server_exceptions=True)

        resp = client.get("/ping")
        assert resp.status_code == 200

        traceparent = resp.headers.get("traceparent")
        assert traceparent is not None, "traceparent header absent"

        parts = traceparent.split("-")
        assert len(parts) == 4, f"Expected 4 parts, got: {traceparent!r}"
        version, trace_id, span_id, flags = parts
        assert version == "00", f"Unexpected version: {version!r}"
        assert len(trace_id) == 32, f"trace_id length != 32: {trace_id!r}"
        assert len(span_id) == 16, f"span_id length != 16: {span_id!r}"
        assert flags == "01", f"Unexpected flags: {flags!r}"

    def test_tracing_sets_state_on_request(self) -> None:
        """TC-GT01b: request.state.trace_id and span_id are set by middleware."""
        app = _make_tracing_app()
        client = TestClient(app, raise_server_exceptions=True)

        resp = client.get("/ping")
        assert resp.status_code == 200

        body = resp.json()
        assert body["trace_id"] is not None, "request.state.trace_id not set"
        assert body["span_id"] is not None, "request.state.span_id not set"
        assert len(body["trace_id"]) == 32
        assert len(body["span_id"]) == 16


# ---------------------------------------------------------------------------
# TC-GT02: Middleware propagates an existing traceparent
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTracingMiddlewarePropagates:
    def test_tracing_middleware_propagates_existing_trace(self) -> None:
        """TC-GT02: Incoming trace_id is preserved in the outbound traceparent."""
        app = _make_tracing_app()
        client = TestClient(app, raise_server_exceptions=True)

        incoming_trace_id = "a" * 32
        incoming_span_id = "b" * 16
        incoming_traceparent = f"00-{incoming_trace_id}-{incoming_span_id}-01"

        resp = client.get("/ping", headers={"traceparent": incoming_traceparent})
        assert resp.status_code == 200

        traceparent = resp.headers.get("traceparent")
        assert traceparent is not None
        parts = traceparent.split("-")
        assert len(parts) == 4
        _, returned_trace_id, returned_span_id, _ = parts

        # trace_id must be the same as what we sent
        assert returned_trace_id == incoming_trace_id, (
            f"trace_id not propagated: expected {incoming_trace_id!r}, got {returned_trace_id!r}"
        )
        # span_id must be a *fresh* span (not the parent span we sent)
        assert returned_span_id != incoming_span_id, (
            "span_id should be a new gateway span, not the incoming parent span"
        )

    def test_tracing_middleware_propagates_trace_id_to_state(self) -> None:
        """TC-GT02b: request.state.trace_id reflects the incoming trace_id."""
        app = _make_tracing_app()
        client = TestClient(app, raise_server_exceptions=True)

        trace_id = "c" * 32
        span_id = "d" * 16
        traceparent = f"00-{trace_id}-{span_id}-01"

        resp = client.get("/ping", headers={"traceparent": traceparent})
        body = resp.json()
        assert body["trace_id"] == trace_id

    def test_malformed_traceparent_creates_new_trace(self) -> None:
        """TC-GT02c: A malformed traceparent falls back to a fresh root trace."""
        app = _make_tracing_app()
        client = TestClient(app, raise_server_exceptions=True)

        resp = client.get("/ping", headers={"traceparent": "not-a-valid-header"})
        assert resp.status_code == 200

        traceparent = resp.headers.get("traceparent")
        assert traceparent is not None
        parts = traceparent.split("-")
        assert len(parts) == 4
        assert parts[0] == "00"


# ---------------------------------------------------------------------------
# TC-GT03: _report_span fire-and-forget (mock urlopen)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestReportSpanFireAndForget:
    def test_report_span_fire_and_forget(self) -> None:
        """TC-GT03: _report_span calls urlopen with correct Zipkin payload."""
        with patch("gateway.middleware.tracing.urlopen") as mock_urlopen:
            with patch("gateway.middleware.tracing.ZIPKIN_ENDPOINT", "http://zipkin:9411/api/v2/spans"):
                _report_span(
                    trace_id="a" * 32,
                    span_id="b" * 16,
                    parent_id=None,
                    name="GET /api/health",
                    duration_us=1234,
                    status_code=200,
                )

        mock_urlopen.assert_called_once()
        call_args = mock_urlopen.call_args
        req_obj = call_args[0][0]

        # Verify the request target
        assert req_obj.full_url == "http://zipkin:9411/api/v2/spans"
        assert req_obj.get_header("Content-type") == "application/json"

        # Verify span payload structure
        payload = json.loads(req_obj.data.decode())
        assert isinstance(payload, list)
        assert len(payload) == 1
        span = payload[0]
        assert span["traceId"] == "a" * 32
        assert span["id"] == "b" * 16
        assert span["name"] == "GET /api/health"
        assert span["duration"] == 1234
        assert span["localEndpoint"]["serviceName"] == "imsp-gateway"
        assert span["tags"]["http.status_code"] == "200"
        assert "parentId" not in span  # no parent

    def test_report_span_includes_parent_id(self) -> None:
        """TC-GT03b: _report_span includes parentId when parent_id is provided."""
        with patch("gateway.middleware.tracing.urlopen") as mock_urlopen:
            with patch("gateway.middleware.tracing.ZIPKIN_ENDPOINT", "http://zipkin:9411/api/v2/spans"):
                _report_span(
                    trace_id="e" * 32,
                    span_id="f" * 16,
                    parent_id="0" * 16,
                    name="POST /api/kg/query",
                    duration_us=5000,
                    status_code=201,
                )

        req_obj = mock_urlopen.call_args[0][0]
        span = json.loads(req_obj.data.decode())[0]
        assert span["parentId"] == "0" * 16

    def test_report_span_silences_urlopen_errors(self) -> None:
        """TC-GT03c: Errors in urlopen are swallowed (fire-and-forget)."""
        with patch("gateway.middleware.tracing.urlopen", side_effect=OSError("network down")):
            with patch("gateway.middleware.tracing.ZIPKIN_ENDPOINT", "http://zipkin:9411/api/v2/spans"):
                # Must not raise
                _report_span(
                    trace_id="1" * 32,
                    span_id="2" * 16,
                    parent_id=None,
                    name="GET /health",
                    duration_us=100,
                    status_code=200,
                )

    def test_report_span_no_op_when_endpoint_empty(self) -> None:
        """TC-GT03d: _report_span is a no-op when ZIPKIN_ENDPOINT is empty string."""
        with patch("gateway.middleware.tracing.urlopen") as mock_urlopen:
            with patch("gateway.middleware.tracing.ZIPKIN_ENDPOINT", ""):
                # Call middleware via the app instead (endpoint guard is in dispatch)
                app = _make_tracing_app()
                client = TestClient(app, raise_server_exceptions=True)
                resp = client.get("/ping")
                assert resp.status_code == 200

        # urlopen should not be called since ZIPKIN_ENDPOINT is empty
        mock_urlopen.assert_not_called()
