"""Extended unit tests for core/kg/api/middleware/audit.py.

Covers the two previously uncovered lines:
- Line 55: excluded prefix path bypass — a POST to /api/v1/health or /metrics
  passes through without emitting an audit log entry.
- Line 94-98: request.state.api_key branch — API key is masked in the audit
  entry produced by _build_audit_entry.

Testing approach:
- AuditMiddleware dispatch is tested via a minimal Starlette app (not the full
  FastAPI app) so the test remains a pure unit test with no Neo4j dependency.
- _build_audit_entry api_key branch is tested directly via the helper function
  with a mock request, matching the pattern used in test_audit_log.py.

All tests are @pytest.mark.unit.
"""
from __future__ import annotations

import logging
from typing import Any
from unittest.mock import patch

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from kg.api.middleware.audit import (
    _EXCLUDED_PREFIXES,
    _build_audit_entry,
    AuditMiddleware,
)


# ---------------------------------------------------------------------------
# Minimal Starlette app with AuditMiddleware
# ---------------------------------------------------------------------------


def _make_audited_app() -> Starlette:
    """Build a minimal Starlette app that registers AuditMiddleware."""

    async def _always_ok(request: Request) -> PlainTextResponse:
        return PlainTextResponse("ok", status_code=200)

    app = Starlette(
        routes=[
            Route("/api/v1/health", _always_ok, methods=["GET", "POST"]),
            Route("/metrics", _always_ok, methods=["GET", "POST"]),
            Route("/docs", _always_ok, methods=["GET", "POST"]),
            Route("/api/v1/nodes", _always_ok, methods=["GET", "POST"]),
        ]
    )
    app.add_middleware(AuditMiddleware)
    return app


# ---------------------------------------------------------------------------
# TestExcludedPrefixBypass (line 55)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExcludedPrefixBypass:
    """AuditMiddleware must NOT emit audit log for excluded prefixes.

    Line 55: ``return await call_next(request)`` is executed when the
    request path starts with one of _EXCLUDED_PREFIXES.  We verify that
    the audit logger is never called for those paths.
    """

    def _client(self) -> TestClient:
        return TestClient(_make_audited_app(), raise_server_exceptions=True)

    def test_post_to_health_does_not_trigger_audit_log(self, caplog: Any) -> None:
        """POST /api/v1/health is excluded and produces no audit log entry."""
        client = self._client()
        with caplog.at_level(logging.INFO, logger="kg.audit"):
            resp = client.post("/api/v1/health")
        assert resp.status_code == 200
        # No audit message should appear in the log
        audit_messages = [r for r in caplog.records if r.name == "kg.audit"]
        assert len(audit_messages) == 0, (
            f"Expected no audit log for /api/v1/health, got: {audit_messages}"
        )

    def test_post_to_metrics_does_not_trigger_audit_log(self, caplog: Any) -> None:
        """POST /metrics is excluded and produces no audit log entry."""
        client = self._client()
        with caplog.at_level(logging.INFO, logger="kg.audit"):
            resp = client.post("/metrics")
        assert resp.status_code == 200
        audit_messages = [r for r in caplog.records if r.name == "kg.audit"]
        assert len(audit_messages) == 0

    def test_post_to_docs_does_not_trigger_audit_log(self, caplog: Any) -> None:
        """POST /docs is excluded and produces no audit log entry."""
        client = self._client()
        with caplog.at_level(logging.INFO, logger="kg.audit"):
            resp = client.post("/docs")
        assert resp.status_code == 200
        audit_messages = [r for r in caplog.records if r.name == "kg.audit"]
        assert len(audit_messages) == 0

    def test_post_to_regular_api_route_does_trigger_audit_log(self, caplog: Any) -> None:
        """POST /api/v1/nodes (not excluded) should produce an audit log entry."""
        client = self._client()
        with caplog.at_level(logging.INFO, logger="kg.audit"):
            resp = client.post("/api/v1/nodes")
        assert resp.status_code == 200
        audit_messages = [r for r in caplog.records if r.name == "kg.audit"]
        assert len(audit_messages) == 1
        assert "AUDIT: POST /api/v1/nodes" in audit_messages[0].message

    def test_excluded_prefixes_set_contains_expected_paths(self) -> None:
        """_EXCLUDED_PREFIXES must contain health, metrics, docs and openapi paths."""
        assert "/api/v1/health" in _EXCLUDED_PREFIXES
        assert "/metrics" in _EXCLUDED_PREFIXES
        assert "/docs" in _EXCLUDED_PREFIXES
        assert "/openapi.json" in _EXCLUDED_PREFIXES
        assert "/redoc" in _EXCLUDED_PREFIXES


# ---------------------------------------------------------------------------
# TestAuditEntryApiKeyBranch (lines 95-98)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAuditEntryApiKeyBranch:
    """Tests for the api_key masking branch in _build_audit_entry (lines 95-98).

    When request.state has ``api_key`` but NOT ``user_id``, the function
    must mask the key and set audit_user to "apikey:***<last-4-chars>".
    """

    def _make_request(self, api_key: str) -> Any:
        """Build a minimal mock request with state.api_key set."""

        class _State:
            pass

        class _URL:
            path = "/api/v1/query"

        class _Request:
            method = "POST"
            url = _URL()
            query_params = None
            headers: dict[str, str] = {}
            client = None
            state = _State()

        req = _Request()
        req.state.api_key = api_key  # type: ignore[attr-defined]
        return req

    def _make_response(self, status_code: int = 200) -> Any:
        class _Response:
            pass

        r = _Response()
        r.status_code = status_code  # type: ignore[attr-defined]
        return r

    def test_api_key_is_masked_with_last_four_chars(self) -> None:
        """API key longer than 4 chars is shown as 'apikey:***<last4>'."""
        req = self._make_request("sk-1234567890abcdef")
        entry = _build_audit_entry(req, self._make_response(), 5.0)
        assert entry["audit_user"] == "apikey:***cdef"

    def test_api_key_short_masked_completely(self) -> None:
        """API key of 4 chars or fewer is masked as 'apikey:***'."""
        req = self._make_request("abcd")
        entry = _build_audit_entry(req, self._make_response(), 5.0)
        assert entry["audit_user"] == "apikey:***"

    def test_api_key_exactly_four_chars_masked_completely(self) -> None:
        """An API key of exactly 4 characters uses the short fallback mask."""
        req = self._make_request("1234")
        entry = _build_audit_entry(req, self._make_response(), 1.0)
        assert entry["audit_user"] == "apikey:***"

    def test_api_key_five_chars_shows_last_four(self) -> None:
        """An API key of 5 chars shows the last 4 with the *** prefix."""
        req = self._make_request("abcde")
        entry = _build_audit_entry(req, self._make_response(), 1.0)
        assert entry["audit_user"] == "apikey:***bcde"

    def test_api_key_branch_does_not_expose_full_key(self) -> None:
        """The full API key must never appear in the audit_user field."""
        secret = "super-secret-api-key-xyz"
        req = self._make_request(secret)
        entry = _build_audit_entry(req, self._make_response(), 1.0)
        assert secret not in entry["audit_user"]

    def test_user_id_takes_precedence_over_api_key(self) -> None:
        """When both user_id and api_key are present, user_id wins."""

        class _State:
            user_id = "user-999"
            api_key = "sk-abc123456789"

        class _URL:
            path = "/api/v1/nodes"

        class _Request:
            method = "DELETE"
            url = _URL()
            query_params = None
            headers: dict[str, str] = {}
            client = None
            state = _State()

        entry = _build_audit_entry(_Request(), self._make_response(204), 3.0)
        # user_id branch is hit first (line 93-94)
        assert entry["audit_user"] == "user-999"
        assert "apikey" not in entry["audit_user"]

    def test_neither_user_id_nor_api_key_yields_empty_string(self) -> None:
        """When neither user_id nor api_key is on state, audit_user is ''."""

        class _State:
            pass

        class _URL:
            path = "/api/v1/nodes"

        class _Request:
            method = "POST"
            url = _URL()
            query_params = None
            headers: dict[str, str] = {}
            client = None
            state = _State()

        entry = _build_audit_entry(_Request(), self._make_response(), 2.0)
        assert entry["audit_user"] == ""
