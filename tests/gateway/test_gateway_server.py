"""Tests for the Gateway FastAPI server."""
from __future__ import annotations

import pytest
import json


class TestGatewayServer:
    """Test gateway server configuration and creation."""

    @pytest.mark.unit
    def test_create_server(self):
        """Server creates successfully with default config."""
        from gateway.server import create_server
        from gateway.config import GatewayConfig

        config = GatewayConfig(port=9999, cors_origins=("http://test.local",))
        server = create_server(config)

        assert server.title == "IMSP API Gateway"

    @pytest.mark.unit
    def test_server_has_routes(self):
        """Server has health, proxy, and WS routes."""
        from gateway.server import create_server
        from gateway.config import GatewayConfig

        config = GatewayConfig(port=9998)
        server = create_server(config)

        route_paths = [r.path for r in server.routes]
        assert "/health" in route_paths
        assert "/ready" in route_paths
        assert "/ws" in route_paths
        assert "/ws/stats" in route_paths

    @pytest.mark.unit
    def test_gateway_cli_entry(self):
        """Gateway __main__ module is importable."""
        from gateway.__main__ import main
        assert callable(main)


class TestHttpxClient:
    """Test that the httpx AsyncClient is wired into the server."""

    @pytest.mark.unit
    def test_httpx_client_created_in_server(self):
        """Server module exposes get_http_client after lifespan startup."""
        from gateway.server import create_server, get_http_client
        from gateway.config import GatewayConfig
        import httpx

        config = GatewayConfig(port=9997)
        server = create_server(config)

        # Use TestClient context manager to trigger lifespan startup/shutdown
        from starlette.testclient import TestClient

        with TestClient(server) as client:
            http_client = get_http_client()
            assert isinstance(http_client, httpx.AsyncClient)

    @pytest.mark.unit
    def test_server_adds_rate_limit_and_request_id_middleware(self):
        """Server registers RateLimitMiddleware and RequestIDMiddleware."""
        from gateway.server import create_server
        from gateway.config import GatewayConfig
        from gateway.middleware.rate_limit import RateLimitMiddleware
        from gateway.middleware.request_id import RequestIDMiddleware

        config = GatewayConfig(port=9996)
        server = create_server(config)

        # user_middleware 는 Middleware(cls=..., options=...) namedtuple 리스트
        middleware_classes = [
            m.cls if hasattr(m, "cls") else type(m)
            for m in server.user_middleware
        ]
        # RateLimitMiddleware 와 RequestIDMiddleware 가 등록돼 있어야 함
        assert RateLimitMiddleware in middleware_classes
        assert RequestIDMiddleware in middleware_classes


class TestKeycloakMiddleware:
    """Test Keycloak JWT middleware."""

    @pytest.mark.unit
    def test_decode_jwt_payload(self):
        """Middleware decodes JWT via JWKS verification."""
        from unittest.mock import patch, MagicMock
        from gateway.middleware.keycloak import KeycloakMiddleware, KeycloakConfig

        middleware = KeycloakMiddleware.__new__(KeycloakMiddleware)
        middleware._config = KeycloakConfig(
            keycloak_url="http://localhost:8180",
            realm="imsp",
            client_id="imsp-api",
        )

        expected_claims = {
            "sub": "user-123",
            "preferred_username": "admin",
            "iss": "http://localhost:8180/realms/imsp",
            "realm_access": {"roles": ["admin"]},
        }

        fake_jwks = {"keys": [{"kid": "test-kid", "kty": "RSA"}]}
        fake_key = MagicMock()

        with patch.object(middleware, "_fetch_jwks", return_value=fake_jwks), \
             patch.object(middleware, "_get_signing_key", return_value=fake_key), \
             patch("jwt.decode", return_value=expected_claims):
            claims = middleware._decode_token("fake.jwt.token")

        assert claims["sub"] == "user-123"
        assert claims["preferred_username"] == "admin"
        assert "admin" in claims["realm_access"]["roles"]

    @pytest.mark.unit
    def test_invalid_jwt_format(self):
        """Middleware rejects invalid tokens via JWKS verification."""
        from unittest.mock import patch, MagicMock
        from gateway.middleware.keycloak import KeycloakMiddleware, KeycloakConfig

        middleware = KeycloakMiddleware.__new__(KeycloakMiddleware)
        middleware._config = KeycloakConfig(
            keycloak_url="http://localhost:8180",
            realm="imsp",
            client_id="imsp-api",
        )

        import jwt as pyjwt
        fake_jwks = {"keys": [{"kid": "test-kid", "kty": "RSA"}]}
        fake_key = MagicMock()

        with patch.object(middleware, "_fetch_jwks", return_value=fake_jwks), \
             patch.object(middleware, "_get_signing_key", return_value=fake_key), \
             patch("jwt.decode", side_effect=pyjwt.InvalidTokenError("bad token")):
            with pytest.raises(ValueError, match="Invalid token"):
                middleware._decode_token("not-a-jwt")

    @pytest.mark.unit
    def test_public_path_detection(self):
        """Middleware correctly identifies public paths."""
        from gateway.middleware.keycloak import KeycloakConfig

        config = KeycloakConfig(
            keycloak_url="http://localhost:8180",
            realm="imsp",
            client_id="imsp-api",
            public_paths=["/health", "/ready", "/docs"],
        )

        assert config.is_public_path("/health") is True
        assert config.is_public_path("/docs") is True
        assert config.is_public_path("/api/v1/query") is False
