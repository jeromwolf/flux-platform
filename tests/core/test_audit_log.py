"""Audit logging middleware unit tests.

TC-AL01 ~ TC-AL06: AuditMiddleware behavior verification.
All tests run without external dependencies.
"""

from __future__ import annotations

import pytest

from kg.api.middleware.audit import (
    AuditMiddleware,
    _AUDITED_METHODS,
    _EXCLUDED_PREFIXES,
    _build_audit_entry,
    _get_client_ip,
)


# =============================================================================
# TC-AL01: Audited methods
# =============================================================================


@pytest.mark.unit
class TestAuditedMethods:
    """Audit method filtering tests."""

    def test_state_changing_methods_are_audited(self) -> None:
        """TC-AL01-a: POST, PUT, PATCH, DELETE are audited."""
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            assert method in _AUDITED_METHODS

    def test_get_not_audited(self) -> None:
        """TC-AL01-b: GET is not audited."""
        assert "GET" not in _AUDITED_METHODS

    def test_options_not_audited(self) -> None:
        """TC-AL01-c: OPTIONS is not audited."""
        assert "OPTIONS" not in _AUDITED_METHODS


# =============================================================================
# TC-AL02: Excluded paths
# =============================================================================


@pytest.mark.unit
class TestExcludedPaths:
    """Path exclusion tests."""

    def test_health_excluded(self) -> None:
        """TC-AL02-a: Health endpoint is excluded."""
        assert any("/api/v1/health".startswith(p) for p in _EXCLUDED_PREFIXES)

    def test_metrics_excluded(self) -> None:
        """TC-AL02-b: Metrics endpoint is excluded."""
        assert any("/metrics".startswith(p) for p in _EXCLUDED_PREFIXES)

    def test_docs_excluded(self) -> None:
        """TC-AL02-c: Docs endpoints are excluded."""
        assert any("/docs".startswith(p) for p in _EXCLUDED_PREFIXES)

    def test_api_route_not_excluded(self) -> None:
        """TC-AL02-d: Regular API routes are not excluded."""
        assert not any("/api/v1/graph/nodes".startswith(p) for p in _EXCLUDED_PREFIXES)


# =============================================================================
# TC-AL03: Client IP extraction
# =============================================================================


@pytest.mark.unit
class TestClientIP:
    """Client IP extraction tests."""

    def test_forwarded_for_first_ip(self) -> None:
        """TC-AL03-a: X-Forwarded-For returns first IP."""

        class MockRequest:
            headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
            client = None

        assert _get_client_ip(MockRequest()) == "1.2.3.4"

    def test_real_ip_header(self) -> None:
        """TC-AL03-b: X-Real-IP is used when X-Forwarded-For is absent."""

        class MockRequest:
            headers = {"X-Real-IP": "10.0.0.1"}
            client = None

        assert _get_client_ip(MockRequest()) == "10.0.0.1"

    def test_direct_client(self) -> None:
        """TC-AL03-c: Falls back to direct client IP."""

        class MockClient:
            host = "127.0.0.1"

        class MockRequest:
            headers: dict[str, str] = {}
            client = MockClient()

        assert _get_client_ip(MockRequest()) == "127.0.0.1"

    def test_no_client_info(self) -> None:
        """TC-AL03-d: Returns empty string when no client info available."""

        class MockRequest:
            headers: dict[str, str] = {}
            client = None

        assert _get_client_ip(MockRequest()) == ""


# =============================================================================
# TC-AL04: Audit entry building
# =============================================================================


@pytest.mark.unit
class TestAuditEntryBuilding:
    """Audit entry construction tests."""

    def test_build_entry_basic(self) -> None:
        """TC-AL04-a: _build_audit_entry extracts correct fields."""

        class MockState:
            request_id = "req-123"

        class MockURL:
            path = "/api/v1/graph/nodes"

        class MockQueryParams:
            def __str__(self) -> str:
                return "limit=10"
            def __bool__(self) -> bool:
                return True

        class MockRequest:
            method = "POST"
            url = MockURL()
            query_params = MockQueryParams()
            state = MockState()
            headers: dict[str, str] = {}
            client = None

        class MockResponse:
            status_code = 201

        entry = _build_audit_entry(MockRequest(), MockResponse(), 42.5)
        assert entry["audit_action"] == "POST"
        assert entry["audit_path"] == "/api/v1/graph/nodes"
        assert entry["audit_status"] == 201
        assert entry["audit_duration_ms"] == 42.5
        assert entry["audit_request_id"] == "req-123"

    def test_build_entry_with_api_key_masking(self) -> None:
        """TC-AL04-b: API key is masked in audit entry."""

        class MockState:
            request_id = ""
            api_key = "sk-1234567890abcdef"

        class MockURL:
            path = "/api/v1/query"

        class MockRequest:
            method = "POST"
            url = MockURL()
            query_params = None
            state = MockState()
            headers: dict[str, str] = {}
            client = None

        class MockResponse:
            status_code = 200

        entry = _build_audit_entry(MockRequest(), MockResponse(), 10.0)
        assert entry["audit_user"] == "apikey:***cdef"
        assert "1234567890" not in entry["audit_user"]
