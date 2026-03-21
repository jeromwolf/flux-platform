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


class TestKeycloakMiddleware:
    """Test Keycloak JWT middleware."""

    @pytest.mark.unit
    def test_decode_jwt_payload(self):
        """Middleware decodes JWT base64 payload."""
        from gateway.middleware.keycloak import KeycloakMiddleware, KeycloakConfig
        import base64

        middleware = KeycloakMiddleware.__new__(KeycloakMiddleware)
        middleware._config = KeycloakConfig(
            keycloak_url="http://localhost:8180",
            realm="imsp",
            client_id="imsp-api",
        )

        # Build a fake 3-part JWT
        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "RS256"}).encode()
        ).decode().rstrip("=")
        payload = base64.urlsafe_b64encode(json.dumps({
            "sub": "user-123",
            "preferred_username": "admin",
            "iss": "http://localhost:8180/realms/imsp",
            "realm_access": {"roles": ["admin"]},
        }).encode()).decode().rstrip("=")
        sig = "fakesig"
        token = f"{header}.{payload}.{sig}"

        claims = middleware._decode_token(token)
        assert claims["sub"] == "user-123"
        assert claims["preferred_username"] == "admin"
        assert "admin" in claims["realm_access"]["roles"]

    @pytest.mark.unit
    def test_invalid_jwt_format(self):
        """Middleware rejects non-3-part tokens."""
        from gateway.middleware.keycloak import KeycloakMiddleware, KeycloakConfig

        middleware = KeycloakMiddleware.__new__(KeycloakMiddleware)
        middleware._config = KeycloakConfig(
            keycloak_url="http://localhost:8180",
            realm="imsp",
            client_id="imsp-api",
        )

        with pytest.raises(ValueError, match="Invalid JWT format"):
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
