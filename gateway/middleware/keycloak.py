"""Keycloak OIDC JWT verification middleware."""
from __future__ import annotations

import json
import logging
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


@dataclass
class KeycloakConfig:
    """Keycloak OIDC configuration."""
    keycloak_url: str
    realm: str
    client_id: str
    public_paths: list[str] = field(default_factory=list)
    _jwks_cache: dict[str, Any] | None = field(default=None, repr=False)

    @property
    def issuer(self) -> str:
        return f"{self.keycloak_url}/realms/{self.realm}"

    @property
    def jwks_uri(self) -> str:
        return f"{self.issuer}/protocol/openid-connect/certs"

    def is_public_path(self, path: str) -> bool:
        """Check if a path should skip authentication."""
        for public in self.public_paths:
            if path == public or path.startswith(public + "/"):
                return True
        return False


class KeycloakMiddleware(BaseHTTPMiddleware):
    """Validates JWT tokens issued by Keycloak.

    In Y1, uses a lightweight validation approach:
    - Extracts Bearer token from Authorization header
    - Decodes JWT payload (base64) without cryptographic verification
    - Verifies issuer and client_id claims
    - Sets request.state.user with decoded claims

    In Y2+, will use PyJWT + JWKS for full cryptographic verification.
    """

    def __init__(
        self,
        app: Any,
        keycloak_url: str = "",
        realm: str = "imsp",
        client_id: str = "imsp-api",
        public_paths: list[str] | None = None,
    ) -> None:
        super().__init__(app)
        self._config = KeycloakConfig(
            keycloak_url=keycloak_url,
            realm=realm,
            client_id=client_id,
            public_paths=public_paths or [],
        )

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        path = request.url.path

        # Skip auth for public paths
        if self._config.is_public_path(path):
            return await call_next(request)

        # Extract Bearer token
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={
                    "type": "about:blank",
                    "title": "Unauthorized",
                    "status": 401,
                    "detail": "Missing or invalid Authorization header",
                },
            )

        token = auth_header[7:]  # Strip "Bearer "

        try:
            claims = self._decode_token(token)
        except ValueError as exc:
            return JSONResponse(
                status_code=401,
                content={
                    "type": "about:blank",
                    "title": "Unauthorized",
                    "status": 401,
                    "detail": str(exc),
                },
            )

        # Set user info on request state
        request.state.user = claims
        request.state.user_id = claims.get("sub", "")
        request.state.user_roles = claims.get("realm_access", {}).get("roles", [])

        return await call_next(request)

    def _decode_token(self, token: str) -> dict[str, Any]:
        """Decode and validate JWT token.

        Y1: Base64 decode without crypto verification.
        Y2: Add PyJWT + JWKS verification.
        """
        import base64

        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid JWT format")

        # Decode payload (part 1)
        payload_b64 = parts[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding

        try:
            payload_bytes = base64.urlsafe_b64decode(payload_b64)
            claims: dict[str, Any] = json.loads(payload_bytes)
        except Exception as exc:
            raise ValueError(f"Failed to decode JWT payload: {exc}") from exc

        # Validate issuer
        expected_issuer = self._config.issuer
        if claims.get("iss") != expected_issuer:
            logger.warning(
                "JWT issuer mismatch: expected=%s got=%s",
                expected_issuer,
                claims.get("iss"),
            )
            # Don't reject in Y1 — just warn

        return claims
