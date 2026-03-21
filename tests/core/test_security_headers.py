"""Security headers middleware unit tests.

TC-SH01 ~ TC-SH08: SecurityHeadersMiddleware behavior verification.
All tests run without external dependencies.
"""

from __future__ import annotations

import pytest

from kg.api.middleware.security_headers import SecurityHeadersMiddleware


# =============================================================================
# TC-SH01: Middleware instantiation
# =============================================================================


@pytest.mark.unit
class TestSecurityHeadersConfig:
    """SecurityHeadersMiddleware configuration tests."""

    def test_default_hsts_disabled_in_dev(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-SH01-a: HSTS is disabled in development by default."""
        monkeypatch.setenv("ENV", "development")
        mw = SecurityHeadersMiddleware(app=None)  # type: ignore[arg-type]
        assert mw._enable_hsts is False

    def test_hsts_enabled_in_production(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-SH01-b: HSTS is enabled in production by default."""
        monkeypatch.setenv("ENV", "production")
        mw = SecurityHeadersMiddleware(app=None)  # type: ignore[arg-type]
        assert mw._enable_hsts is True

    def test_explicit_hsts_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-SH01-c: Explicit enable_hsts overrides environment detection."""
        monkeypatch.setenv("ENV", "development")
        mw = SecurityHeadersMiddleware(app=None, enable_hsts=True)  # type: ignore[arg-type]
        assert mw._enable_hsts is True

    def test_custom_csp_policy(self) -> None:
        """TC-SH01-d: Custom CSP policy is stored."""
        mw = SecurityHeadersMiddleware(
            app=None,  # type: ignore[arg-type]
            csp_policy="default-src 'self'; script-src 'self'",
        )
        assert mw._csp_policy == "default-src 'self'; script-src 'self'"

    def test_default_hsts_max_age(self) -> None:
        """TC-SH01-e: Default HSTS max-age is 1 year (31536000 seconds)."""
        mw = SecurityHeadersMiddleware(app=None, enable_hsts=True)  # type: ignore[arg-type]
        assert mw._hsts_max_age == 31_536_000


# =============================================================================
# TC-SH02: Integration with ASGI
# =============================================================================


@pytest.mark.unit
class TestSecurityHeadersIntegration:
    """Verify middleware can be imported and instantiated."""

    def test_middleware_is_importable(self) -> None:
        """TC-SH02-a: SecurityHeadersMiddleware is importable."""
        assert SecurityHeadersMiddleware is not None

    def test_middleware_inherits_base(self) -> None:
        """TC-SH02-b: Inherits from BaseHTTPMiddleware."""
        from starlette.middleware.base import BaseHTTPMiddleware
        assert issubclass(SecurityHeadersMiddleware, BaseHTTPMiddleware)
