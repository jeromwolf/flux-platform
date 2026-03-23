"""Tests for gateway middleware: RateLimitMiddleware and RequestIDMiddleware."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from starlette.requests import Request
from starlette.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers — minimal FastAPI test apps
# ---------------------------------------------------------------------------


def _make_rate_limit_app(requests_per_minute: int = 5) -> FastAPI:
    """Create a minimal app with RateLimitMiddleware for testing.

    Args:
        requests_per_minute: Limit injected into :class:`RateLimitConfig`.

    Returns:
        A :class:`FastAPI` app with rate limiting configured.
    """
    from gateway.middleware.rate_limit import RateLimitConfig, RateLimitMiddleware

    app = FastAPI()
    config = RateLimitConfig(
        requests_per_minute=requests_per_minute,
        exclude_paths=["/health"],
    )
    app.add_middleware(RateLimitMiddleware, config=config)

    @app.get("/api/test")
    async def _test():
        return {"ok": True}

    @app.get("/health")
    async def _health():
        return {"status": "ok"}

    return app


def _make_request_id_app() -> FastAPI:
    """Create a minimal app with RequestIDMiddleware for testing.

    Returns:
        A :class:`FastAPI` app with request-ID tracking configured.
    """
    from gateway.middleware.request_id import RequestIDMiddleware

    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/ping")
    async def _ping(request: Request):
        return {"request_id": request.state.request_id}

    return app


# ---------------------------------------------------------------------------
# RateLimitMiddleware tests
# ---------------------------------------------------------------------------


class TestRateLimitMiddleware:
    """Tests for the sliding-window RateLimitMiddleware."""

    @pytest.mark.unit
    def test_tc_rl01_requests_within_limit_pass(self):
        """TC-RL01: Requests within the limit pass through with 200."""
        app = _make_rate_limit_app(requests_per_minute=10)
        client = TestClient(app, raise_server_exceptions=True)

        for _ in range(5):
            resp = client.get("/api/test")
            assert resp.status_code == 200

    @pytest.mark.unit
    def test_tc_rl02_requests_over_limit_get_429(self):
        """TC-RL02: Requests exceeding the limit receive 429."""
        app = _make_rate_limit_app(requests_per_minute=3)
        client = TestClient(app, raise_server_exceptions=True)

        # 허용 한도까지는 통과
        for _ in range(3):
            resp = client.get("/api/test")
            assert resp.status_code == 200

        # 초과 요청은 429 반환
        resp = client.get("/api/test")
        assert resp.status_code == 429

        body = resp.json()
        assert body["status"] == 429
        assert body["title"] == "Too Many Requests"

    @pytest.mark.unit
    def test_tc_rl03_excluded_paths_bypass_rate_limiting(self):
        """TC-RL03: Paths in exclude_paths bypass rate limiting entirely."""
        # 매우 낮은 한도 설정 — 제외 경로는 영향 없어야 함
        app = _make_rate_limit_app(requests_per_minute=1)
        client = TestClient(app, raise_server_exceptions=True)

        # /health 는 제외 경로 — 몇 번을 호출해도 429 가 아님
        for _ in range(10):
            resp = client.get("/health")
            assert resp.status_code == 200

    @pytest.mark.unit
    def test_tc_rl04_rate_limit_headers_present(self):
        """TC-RL04: Rate-limit headers are present in passing responses."""
        app = _make_rate_limit_app(requests_per_minute=10)
        client = TestClient(app, raise_server_exceptions=True)

        resp = client.get("/api/test")
        assert resp.status_code == 200
        assert "X-RateLimit-Limit" in resp.headers
        assert "X-RateLimit-Remaining" in resp.headers
        assert "X-RateLimit-Reset" in resp.headers

        assert resp.headers["X-RateLimit-Limit"] == "10"
        # Remaining 은 정수여야 함
        remaining = int(resp.headers["X-RateLimit-Remaining"])
        assert 0 <= remaining <= 10

    @pytest.mark.unit
    def test_tc_rl04_rate_limit_headers_in_429(self):
        """TC-RL04 (429 variant): Rate-limit headers present in 429 responses."""
        app = _make_rate_limit_app(requests_per_minute=1)
        client = TestClient(app, raise_server_exceptions=True)

        client.get("/api/test")  # 한도 소진
        resp = client.get("/api/test")
        assert resp.status_code == 429
        assert "X-RateLimit-Limit" in resp.headers
        assert resp.headers["X-RateLimit-Remaining"] == "0"
        assert "X-RateLimit-Reset" in resp.headers

    @pytest.mark.unit
    def test_tc_rl05_different_clients_independent_limits(self):
        """TC-RL05: Different client IPs have independent rate-limit windows."""
        from gateway.middleware.rate_limit import RateLimitConfig, RateLimitMiddleware

        app = FastAPI()
        config = RateLimitConfig(
            requests_per_minute=2,
            exclude_paths=[],
        )
        app.add_middleware(RateLimitMiddleware, config=config)

        @app.get("/check")
        async def _check():
            return {"ok": True}

        client = TestClient(app, raise_server_exceptions=True)

        # client_a が한도 2를 소진
        for _ in range(2):
            resp = client.get("/check", headers={"X-Forwarded-For": "10.0.0.1"})
            assert resp.status_code == 200

        # client_a 는 이제 429
        resp_a_blocked = client.get("/check", headers={"X-Forwarded-For": "10.0.0.1"})
        assert resp_a_blocked.status_code == 429

        # client_b 는 아직 통과 가능
        resp_b = client.get("/check", headers={"X-Forwarded-For": "10.0.0.2"})
        assert resp_b.status_code == 200


# ---------------------------------------------------------------------------
# RequestIDMiddleware tests
# ---------------------------------------------------------------------------


class TestRequestIDMiddleware:
    """Tests for the RequestIDMiddleware."""

    @pytest.mark.unit
    def test_tc_ri01_response_includes_request_id_header(self):
        """TC-RI01: Every response carries an X-Request-ID header."""
        app = _make_request_id_app()
        client = TestClient(app, raise_server_exceptions=True)

        resp = client.get("/ping")
        assert resp.status_code == 200
        assert "X-Request-ID" in resp.headers
        assert len(resp.headers["X-Request-ID"]) > 0

    @pytest.mark.unit
    def test_tc_ri02_client_provided_request_id_preserved(self):
        """TC-RI02: A client-supplied X-Request-ID is echoed back unchanged."""
        app = _make_request_id_app()
        client = TestClient(app, raise_server_exceptions=True)

        custom_id = "my-trace-abc123"
        resp = client.get("/ping", headers={"X-Request-ID": custom_id})
        assert resp.status_code == 200
        assert resp.headers["X-Request-ID"] == custom_id

        # 핸들러에서도 동일 ID 확인
        body = resp.json()
        assert body["request_id"] == custom_id

    @pytest.mark.unit
    def test_tc_ri03_auto_generated_id_is_valid_uuid_hex(self):
        """TC-RI03: Auto-generated X-Request-ID is a 32-char lowercase hex string."""
        app = _make_request_id_app()
        client = TestClient(app, raise_server_exceptions=True)

        resp = client.get("/ping")
        assert resp.status_code == 200

        request_id = resp.headers["X-Request-ID"]
        # uuid4().hex 는 32자리 소문자 16진수
        assert len(request_id) == 32
        assert all(c in "0123456789abcdef" for c in request_id)

    @pytest.mark.unit
    def test_tc_ri04_request_state_contains_id(self):
        """TC-RI04: request.state.request_id matches the response header."""
        app = _make_request_id_app()
        client = TestClient(app, raise_server_exceptions=True)

        resp = client.get("/ping")
        body = resp.json()
        assert body["request_id"] == resp.headers["X-Request-ID"]
