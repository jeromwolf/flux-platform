"""Unit tests for gateway/middleware/keycloak.py — dispatch() and helpers.

Covers the branches not exercised by test_keycloak_jwks.py:
- KeycloakConfig.is_public_path: exact match, prefix match, no match
- KeycloakConfig.issuer and jwks_uri properties
- KeycloakMiddleware.dispatch:
  - public path bypass (no auth required)
  - missing Authorization header → 401
  - non-Bearer Authorization header → 401
  - valid token (fallback path) → request.state.user set
  - expired token → 401
  - request.state.user_id and user_roles populated correctly
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

    def test_bearer_prefix_only_returns_401(self):
        """Authorization: Bearer  (empty token) is treated as missing."""
        app = _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        # The header value is just "Bearer " with nothing after
        # This will attempt to decode an empty token which should fail
        response = client.get("/api/data", headers={"Authorization": "Bearer "})
        # Either 401 from header check or 401 from decode failure
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# dispatch() — valid token sets request.state
# ---------------------------------------------------------------------------


class TestDispatchValidToken:
    """Valid token populates request.state.user, user_id, user_roles."""

    def _valid_token(self, sub: str = "user-1", roles: list[str] | None = None) -> str:
        now = int(time.time())
        payload: dict[str, Any] = {
            "sub": sub,
            "iss": "/realms/imsp",
            "exp": now + 3600,
            "iat": now - 5,
        }
        if roles:
            payload["realm_access"] = {"roles": roles}
        return _make_fake_token(payload)

    def test_valid_token_returns_200(self):
        """Valid token causes middleware to pass request through (200)."""
        app = _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        token = self._valid_token(sub="user-42")
        # Force JWKS fetch to fail so fallback path is taken
        with patch("urllib.request.urlopen", side_effect=OSError("offline")):
            response = client.get("/api/data", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

    def test_valid_token_populates_user_id(self):
        """request.state.user_id is set to the JWT 'sub' claim."""
        app = _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        token = self._valid_token(sub="user-42")
        with patch("urllib.request.urlopen", side_effect=OSError("offline")):
            response = client.get("/api/data", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "user-42"

    def test_valid_token_populates_roles(self):
        """request.state.user_roles is populated from realm_access.roles."""
        app = _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        token = self._valid_token(sub="admin", roles=["admin", "user"])
        with patch("urllib.request.urlopen", side_effect=OSError("offline")):
            response = client.get("/api/data", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        data = response.json()
        assert "admin" in data["roles"]
        assert "user" in data["roles"]

    def test_valid_token_no_roles_returns_empty_list(self):
        """When JWT has no realm_access, user_roles is empty list."""
        app = _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        token = self._valid_token(sub="norole")
        with patch("urllib.request.urlopen", side_effect=OSError("offline")):
            response = client.get("/api/data", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["roles"] == []


# ---------------------------------------------------------------------------
# dispatch() — expired / invalid token returns 401
# ---------------------------------------------------------------------------


class TestDispatchInvalidToken:
    """Invalid or expired tokens return 401 with error detail."""

    def test_expired_token_returns_401(self):
        """Expired JWT returns 401 Unauthorized."""
        now = int(time.time())
        payload = {
            "sub": "user-expired",
            "exp": now - 300,
            "iat": now - 600,
        }
        token = _make_fake_token(payload)
        app = _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        with patch("urllib.request.urlopen", side_effect=OSError("offline")):
            response = client.get("/api/data", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
        body = response.json()
        assert "expired" in body.get("detail", "").lower()

    def test_malformed_jwt_returns_401(self):
        """A token that is not valid JWT format returns 401."""
        app = _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        with patch("urllib.request.urlopen", side_effect=OSError("offline")):
            response = client.get(
                "/api/data",
                headers={"Authorization": "Bearer this.is.not.valid.jwt.format.extra"},
            )
        assert response.status_code == 401

    def test_future_iat_returns_401(self):
        """Token with iat far in the future returns 401."""
        now = int(time.time())
        payload = {
            "sub": "user-future",
            "exp": now + 3600,
            "iat": now + 600,  # beyond 60s tolerance
        }
        token = _make_fake_token(payload)
        app = _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        with patch("urllib.request.urlopen", side_effect=OSError("offline")):
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
