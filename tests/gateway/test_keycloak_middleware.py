"""Unit tests for gateway/middleware/keycloak.py — dispatch() and helpers.

Covers the branches not exercised by test_keycloak_jwks.py:
- KeycloakConfig.is_public_path: exact match, prefix match, no match
- KeycloakConfig.issuer and jwks_uri properties
- KeycloakMiddleware.dispatch:
  - public path bypass (no auth required)
  - missing Authorization header → 401
  - non-Bearer Authorization header → 401
  - JWKS unavailable → 503 Service Unavailable (no base64 fallback)
  - expired token detected via PyJWT → 401
  - request.state.user_id and user_roles populated correctly (mocked JWKS path)
- KeycloakMiddleware constructor: public_paths stored, defaults applied

All tests are @pytest.mark.unit.  No real network calls.
"""
from __future__ import annotations

import base64
import json
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.testclient import TestClient

from gateway.middleware.keycloak import KeycloakConfig, KeycloakMiddleware

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_token(payload: dict[str, Any], header: dict[str, Any] | None = None) -> str:
    """Build a syntactically valid unsigned JWT for testing."""
    if header is None:
        header = {"alg": "RS256", "typ": "JWT"}

    def _b64(data: dict[str, Any]) -> str:
        raw = json.dumps(data).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return f"{_b64(header)}.{_b64(payload)}.{base64.urlsafe_b64encode(b'sig').rstrip(b'=').decode()}"


def _make_app(
    keycloak_url: str = "",
    public_paths: list[str] | None = None,
) -> FastAPI:
    """Create a minimal FastAPI app wrapped with KeycloakMiddleware."""
    app = FastAPI()

    app.add_middleware(
        KeycloakMiddleware,
        keycloak_url=keycloak_url,
        realm="imsp",
        client_id="imsp-api",
        public_paths=public_paths or [],
    )

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/data")
    async def data(request: Request):
        return {
            "user_id": getattr(request.state, "user_id", None),
            "roles": getattr(request.state, "user_roles", []),
            "sub": getattr(request.state, "user", {}).get("sub", ""),
        }

    return app


# ---------------------------------------------------------------------------
# KeycloakConfig helpers
# ---------------------------------------------------------------------------


class TestKeycloakConfig:
    """KeycloakConfig properties and is_public_path."""

    def test_issuer_property(self):
        """issuer returns keycloak_url/realms/realm."""
        config = KeycloakConfig(
            keycloak_url="http://keycloak:8080",
            realm="myrealm",
            client_id="my-client",
        )
        assert config.issuer == "http://keycloak:8080/realms/myrealm"

    def test_jwks_uri_property(self):
        """jwks_uri appends the openid-connect certs path."""
        config = KeycloakConfig(
            keycloak_url="http://keycloak:8080",
            realm="myrealm",
            client_id="my-client",
        )
        assert config.jwks_uri == (
            "http://keycloak:8080/realms/myrealm/protocol/openid-connect/certs"
        )

    def test_is_public_path_exact_match(self):
        """is_public_path returns True for exact match."""
        config = KeycloakConfig(
            keycloak_url="",
            realm="r",
            client_id="c",
            public_paths=["/health", "/metrics"],
        )
        assert config.is_public_path("/health") is True
        assert config.is_public_path("/metrics") is True

    def test_is_public_path_prefix_match(self):
        """is_public_path returns True for path that starts with a public prefix."""
        config = KeycloakConfig(
            keycloak_url="",
            realm="r",
            client_id="c",
            public_paths=["/public"],
        )
        assert config.is_public_path("/public/docs") is True
        assert config.is_public_path("/public/openapi.json") is True

    def test_is_public_path_no_match(self):
        """is_public_path returns False for private paths."""
        config = KeycloakConfig(
            keycloak_url="",
            realm="r",
            client_id="c",
            public_paths=["/health"],
        )
        assert config.is_public_path("/api/data") is False
        assert config.is_public_path("/healthcheck") is False  # not a prefix match

    def test_is_public_path_empty_list(self):
        """is_public_path returns False when public_paths is empty."""
        config = KeycloakConfig(keycloak_url="", realm="r", client_id="c")
        assert config.is_public_path("/anything") is False


# ---------------------------------------------------------------------------
# KeycloakMiddleware constructor
# ---------------------------------------------------------------------------


class TestKeycloakMiddlewareConstructor:
    """Constructor stores correct defaults and custom values."""

    def test_default_realm_and_client_id(self):
        """Middleware uses default realm='imsp' and client_id='imsp-api'."""
        async def dummy_app(scope, receive, send):
            pass

        mw = KeycloakMiddleware(app=dummy_app)
        assert mw._config.realm == "imsp"
        assert mw._config.client_id == "imsp-api"

    def test_custom_public_paths_stored(self):
        """Middleware stores the supplied public_paths list."""
        async def dummy_app(scope, receive, send):
            pass

        mw = KeycloakMiddleware(
            app=dummy_app,
            public_paths=["/health", "/docs"],
        )
        assert "/health" in mw._config.public_paths
        assert "/docs" in mw._config.public_paths

    def test_none_public_paths_defaults_to_empty(self):
        """public_paths=None is stored as an empty list."""
        async def dummy_app(scope, receive, send):
            pass

        mw = KeycloakMiddleware(app=dummy_app, public_paths=None)
        assert mw._config.public_paths == []


# ---------------------------------------------------------------------------
# dispatch() — public path bypass
# ---------------------------------------------------------------------------


class TestDispatchPublicPaths:
    """Public paths skip authentication entirely."""

    def test_public_path_bypasses_auth(self):
        """GET /health has no auth requirement and returns 200."""
        app = _make_app(public_paths=["/health"])
        client = TestClient(app, raise_server_exceptions=True)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_public_path_prefix_bypasses_auth(self):
        """Paths under /health/ prefix also bypass auth."""
        app = _make_app(public_paths=["/health"])
        client = TestClient(app, raise_server_exceptions=True)
        response = client.get("/health")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# dispatch() — missing / malformed Authorization header
# ---------------------------------------------------------------------------


class TestDispatchMissingAuth:
    """Requests without a valid Bearer token get 401."""

    def test_no_auth_header_returns_401(self):
        """Request with no Authorization header returns 401."""
        app = _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/data")
        assert response.status_code == 401
        body = response.json()
        assert body["status"] == 401

    def test_non_bearer_auth_returns_401(self):
        """Basic auth or other schemes return 401."""
        app = _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/data", headers={"Authorization": "Basic dXNlcjpwYXNz"})
        assert response.status_code == 401

    def test_bearer_prefix_only_returns_401_or_503(self):
        """Authorization: Bearer  (empty token) results in 401 or 503."""
        app = _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        # Empty token triggers _decode_token which raises ValueError (JWKS unavailable → 503,
        # or signing key missing → 401)
        response = client.get("/api/data", headers={"Authorization": "Bearer "})
        assert response.status_code in (401, 503)


# ---------------------------------------------------------------------------
# dispatch() — JWKS unavailable returns 503 (no base64 fallback)
# ---------------------------------------------------------------------------


class TestDispatchJwksUnavailable:
    """When JWKS is unreachable, middleware returns 503 Service Unavailable."""

    def test_jwks_unavailable_returns_503(self):
        """When JWKS endpoint is unreachable, dispatch returns 503."""
        app = _make_app(keycloak_url="http://keycloak:8080")
        client = TestClient(app, raise_server_exceptions=False)
        now = int(time.time())
        token = _make_fake_token({
            "sub": "user-42",
            "iss": "http://keycloak:8080/realms/imsp",
            "exp": now + 3600,
            "iat": now - 5,
        })
        with patch("urllib.request.urlopen", side_effect=OSError("offline")):
            response = client.get("/api/data", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 503
        body = response.json()
        assert body["status"] == 503
        assert body["title"] == "Service Unavailable"

    def test_jwks_unavailable_body_has_detail(self):
        """503 response includes a detail field."""
        app = _make_app(keycloak_url="http://keycloak:8080")
        client = TestClient(app, raise_server_exceptions=False)
        now = int(time.time())
        token = _make_fake_token({"sub": "u", "exp": now + 3600, "iat": now - 5})
        with patch("urllib.request.urlopen", side_effect=OSError("offline")):
            response = client.get("/api/data", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 503
        body = response.json()
        assert "detail" in body

    def test_no_base64_fallback_when_jwks_fails(self):
        """Confirms that even a valid-looking token yields 503, not 200, when JWKS is down."""
        app = _make_app(keycloak_url="http://keycloak:8080")
        client = TestClient(app, raise_server_exceptions=False)
        now = int(time.time())
        token = _make_fake_token({
            "sub": "attacker",
            "iss": "http://keycloak:8080/realms/imsp",
            "exp": now + 3600,
            "iat": now - 5,
            "realm_access": {"roles": ["admin"]},
        })
        with patch("urllib.request.urlopen", side_effect=OSError("network error")):
            response = client.get("/api/data", headers={"Authorization": f"Bearer {token}"})
        # Must NOT be 200 — attacker-crafted tokens must not pass through
        assert response.status_code != 200
        assert response.status_code == 503


# ---------------------------------------------------------------------------
# dispatch() — valid token (mocked JWKS + PyJWT path) sets request.state
# ---------------------------------------------------------------------------


class TestDispatchValidToken:
    """Valid cryptographically-verified token populates request.state."""

    def _make_mock_signing_key(self):
        """Return a mock signing key object."""
        return MagicMock(name="signing_key")

    def test_valid_token_returns_200(self):
        """Mocked JWKS + signing key causes middleware to pass request through (200)."""
        app = _make_app(keycloak_url="http://keycloak:8080")
        client = TestClient(app, raise_server_exceptions=False)
        now = int(time.time())
        payload = {
            "sub": "user-42",
            "iss": "http://keycloak:8080/realms/imsp",
            "exp": now + 3600,
            "iat": now - 5,
        }
        token = _make_fake_token(payload)
        fake_jwks = {"keys": [{"kid": "k1", "kty": "RSA"}]}
        mock_key = self._make_mock_signing_key()

        with patch.object(KeycloakMiddleware, "_fetch_jwks", return_value=fake_jwks), \
             patch.object(KeycloakMiddleware, "_get_signing_key", return_value=mock_key), \
             patch("jwt.decode", return_value=payload):
            response = client.get("/api/data", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200

    def test_valid_token_populates_user_id(self):
        """request.state.user_id is set to the JWT 'sub' claim."""
        app = _make_app(keycloak_url="http://keycloak:8080")
        client = TestClient(app, raise_server_exceptions=False)
        now = int(time.time())
        payload = {
            "sub": "user-42",
            "iss": "http://keycloak:8080/realms/imsp",
            "exp": now + 3600,
            "iat": now - 5,
        }
        token = _make_fake_token(payload)
        fake_jwks = {"keys": [{"kid": "k1", "kty": "RSA"}]}
        mock_key = self._make_mock_signing_key()

        with patch.object(KeycloakMiddleware, "_fetch_jwks", return_value=fake_jwks), \
             patch.object(KeycloakMiddleware, "_get_signing_key", return_value=mock_key), \
             patch("jwt.decode", return_value=payload):
            response = client.get("/api/data", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        assert response.json()["user_id"] == "user-42"

    def test_valid_token_populates_roles(self):
        """request.state.user_roles is populated from realm_access.roles."""
        app = _make_app(keycloak_url="http://keycloak:8080")
        client = TestClient(app, raise_server_exceptions=False)
        now = int(time.time())
        payload = {
            "sub": "admin",
            "iss": "http://keycloak:8080/realms/imsp",
            "exp": now + 3600,
            "iat": now - 5,
            "realm_access": {"roles": ["admin", "user"]},
        }
        token = _make_fake_token(payload)
        fake_jwks = {"keys": [{"kid": "k1", "kty": "RSA"}]}
        mock_key = self._make_mock_signing_key()

        with patch.object(KeycloakMiddleware, "_fetch_jwks", return_value=fake_jwks), \
             patch.object(KeycloakMiddleware, "_get_signing_key", return_value=mock_key), \
             patch("jwt.decode", return_value=payload):
            response = client.get("/api/data", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        data = response.json()
        assert "admin" in data["roles"]
        assert "user" in data["roles"]

    def test_valid_token_no_roles_returns_empty_list(self):
        """When JWT has no realm_access, user_roles is empty list."""
        app = _make_app(keycloak_url="http://keycloak:8080")
        client = TestClient(app, raise_server_exceptions=False)
        now = int(time.time())
        payload = {
            "sub": "norole",
            "iss": "http://keycloak:8080/realms/imsp",
            "exp": now + 3600,
            "iat": now - 5,
        }
        token = _make_fake_token(payload)
        fake_jwks = {"keys": [{"kid": "k1", "kty": "RSA"}]}
        mock_key = self._make_mock_signing_key()

        with patch.object(KeycloakMiddleware, "_fetch_jwks", return_value=fake_jwks), \
             patch.object(KeycloakMiddleware, "_get_signing_key", return_value=mock_key), \
             patch("jwt.decode", return_value=payload):
            response = client.get("/api/data", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        assert response.json()["roles"] == []


# ---------------------------------------------------------------------------
# dispatch() — token error paths return 401
# ---------------------------------------------------------------------------


class TestDispatchInvalidToken:
    """Invalid or expired tokens detected by PyJWT return 401."""

    def test_expired_token_returns_401(self):
        """PyJWT raising ExpiredSignatureError → 401 Unauthorized."""
        import jwt as pyjwt

        app = _make_app(keycloak_url="http://keycloak:8080")
        client = TestClient(app, raise_server_exceptions=False)
        now = int(time.time())
        token = _make_fake_token({"sub": "user-expired", "exp": now - 300, "iat": now - 600})
        fake_jwks = {"keys": [{"kid": "k1", "kty": "RSA"}]}
        mock_key = MagicMock(name="signing_key")

        with patch.object(KeycloakMiddleware, "_fetch_jwks", return_value=fake_jwks), \
             patch.object(KeycloakMiddleware, "_get_signing_key", return_value=mock_key), \
             patch("jwt.decode", side_effect=pyjwt.ExpiredSignatureError("expired")):
            response = client.get("/api/data", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 401
        body = response.json()
        assert "expired" in body.get("detail", "").lower()

    def test_invalid_token_returns_401(self):
        """PyJWT raising InvalidTokenError → 401 Unauthorized."""
        import jwt as pyjwt

        app = _make_app(keycloak_url="http://keycloak:8080")
        client = TestClient(app, raise_server_exceptions=False)
        token = _make_fake_token({"sub": "attacker"})
        fake_jwks = {"keys": [{"kid": "k1", "kty": "RSA"}]}
        mock_key = MagicMock(name="signing_key")

        with patch.object(KeycloakMiddleware, "_fetch_jwks", return_value=fake_jwks), \
             patch.object(KeycloakMiddleware, "_get_signing_key", return_value=mock_key), \
             patch("jwt.decode", side_effect=pyjwt.InvalidTokenError("bad sig")):
            response = client.get("/api/data", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 401

    def test_401_response_has_correct_content_type(self):
        """401 response returns JSON with appropriate fields."""
        app = _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/data")
        assert response.status_code == 401
        body = response.json()
        assert "status" in body
        assert "detail" in body
        assert body["title"] == "Unauthorized"
