"""Keycloak OIDC JWT verification middleware."""
from __future__ import annotations

import json
import logging
import time
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
    _jwks_cached_at: float = field(default=0.0, repr=False)

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

    def clear_jwks_cache(self) -> None:
        """Clear the cached JWKS data (useful for testing or key rotation)."""
        self._jwks_cache = None
        self._jwks_cached_at = 0.0


_JWKS_CACHE_TTL = 3600  # 1 hour in seconds


class KeycloakMiddleware(BaseHTTPMiddleware):
    """Validates JWT tokens issued by Keycloak.

    Performs cryptographic RS256 JWKS verification only.
    No fallback — if Keycloak JWKS is unavailable, returns 503.

    - Extracts Bearer token from Authorization header
    - Decodes JWT payload with RS256 JWKS verification
    - Sets request.state.user with decoded claims
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
            error_msg = str(exc)
            if "service unavailable" in error_msg.lower():
                return JSONResponse(
                    status_code=503,
                    content={
                        "type": "about:blank",
                        "title": "Service Unavailable",
                        "status": 503,
                        "detail": "Authentication service temporarily unavailable",
                    },
                )
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
        """Decode and validate JWT token using PyJWT + JWKS cryptographic verification.

        Raises:
            ValueError: If the token cannot be cryptographically verified.
        """
        try:
            import jwt  # PyJWT
        except ImportError:
            raise ValueError("Authentication service unavailable: PyJWT not installed")

        jwks = self._fetch_jwks()
        if not jwks:
            raise ValueError("Authentication service unavailable: cannot fetch JWKS from Keycloak")

        signing_key = self._get_signing_key(token, jwks)
        if not signing_key:
            raise ValueError("Token verification failed: no matching signing key")

        try:
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=self._config.client_id,
                options={"verify_aud": False},  # Keycloak puts audience in azp, not aud
                issuer=self._config.issuer,
            )
            logger.debug("JWT verified via JWKS for sub=%s", claims.get("sub"))
            return claims
        except jwt.ExpiredSignatureError:
            raise ValueError("Token expired")
        except jwt.InvalidTokenError as e:
            raise ValueError(f"Invalid token: {e}")

    def _fetch_jwks(self) -> dict[str, Any] | None:
        """Fetch JWKS from Keycloak (cached with TTL).

        Returns:
            Parsed JWKS dict if successful, None if fetch fails.
        """
        if (
            self._config._jwks_cache is not None
            and (time.time() - self._config._jwks_cached_at) < _JWKS_CACHE_TTL
        ):
            return self._config._jwks_cache

        try:
            req = urllib.request.Request(self._config.jwks_uri)
            with urllib.request.urlopen(req, timeout=5) as resp:
                jwks = json.loads(resp.read())
                self._config._jwks_cache = jwks
                self._config._jwks_cached_at = time.time()
                logger.info(
                    "JWKS fetched from %s (%d keys)",
                    self._config.jwks_uri,
                    len(jwks.get("keys", [])),
                )
                return jwks
        except Exception as exc:
            logger.warning("Failed to fetch JWKS from %s: %s", self._config.jwks_uri, exc)
            return None

    def _get_signing_key(self, token: str, jwks: dict[str, Any]) -> Any:
        """Extract the signing key from JWKS matching the token's kid.

        Args:
            token: Raw JWT string.
            jwks: Parsed JWKS dict from Keycloak.

        Returns:
            Public key object for PyJWT verification, or None if not found.
        """
        import jwt  # PyJWT

        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")

            for key_data in jwks.get("keys", []):
                if key_data.get("kid") == kid:
                    from jwt.algorithms import RSAAlgorithm
                    return RSAAlgorithm.from_jwk(key_data)

            logger.warning("No matching key found for kid=%s", kid)
            return None
        except Exception as exc:
            logger.warning("Failed to extract signing key: %s", exc)
            return None
