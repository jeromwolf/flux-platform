"""Unit tests for the Request ID middleware."""
from __future__ import annotations

import pytest
from starlette.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from kg.api.middleware.request_id import RequestIdMiddleware


def _test_app():
    """Create a minimal test app with RequestIdMiddleware."""
    async def homepage(request):
        rid = getattr(request.state, "request_id", "missing")
        return JSONResponse({"request_id": rid})

    app = Starlette(routes=[Route("/", homepage)])
    app.add_middleware(RequestIdMiddleware)
    return app


@pytest.mark.unit
class TestRequestIdMiddleware:
    """Tests for RequestIdMiddleware."""

    def test_generates_request_id(self):
        """X-Request-ID가 없으면 자동 생성."""
        client = TestClient(_test_app())
        resp = client.get("/")
        assert resp.status_code == 200
        assert "X-Request-ID" in resp.headers
        assert len(resp.headers["X-Request-ID"]) > 0

    def test_preserves_existing_request_id(self):
        """클라이언트가 제공한 X-Request-ID 보존."""
        client = TestClient(_test_app())
        resp = client.get("/", headers={"X-Request-ID": "my-custom-id"})
        assert resp.headers["X-Request-ID"] == "my-custom-id"

    def test_request_id_available_in_state(self):
        """request.state.request_id에서 접근 가능."""
        client = TestClient(_test_app())
        resp = client.get("/")
        body = resp.json()
        assert body["request_id"] == resp.headers["X-Request-ID"]

    def test_unique_ids_per_request(self):
        """각 요청마다 고유한 ID 생성."""
        client = TestClient(_test_app())
        ids = {client.get("/").headers["X-Request-ID"] for _ in range(5)}
        assert len(ids) == 5  # all unique
