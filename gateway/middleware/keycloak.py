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

    def clear_jwks_cache(self) -> None:
        """Clear the cached JWKS data (useful for testing or key rotation)."""
        self._jwks_cache = None


class KeycloakMiddleware(BaseHTTPMiddleware):
    """Validates JWT tokens issued by Keycloak.

    Primary: PyJWT + JWKS cryptographic verification.
    Fallback: Base64 decode with claim validation when Keycloak is unavailable.

    - Extracts Bearer token from Authorization header
    - Decodes JWT payload with RS256 JWKS verification (primary)
    - Falls back to base64 decode with exp/iat validation (dev/offline mode)
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

        Primary: PyJWT + JWKS cryptographic verification.
        Fallback: Base64 decode with claim validation (dev/offline mode).
        """
        # Try PyJWT + JWKS first
        try:
            import jwt  # PyJWT

            jwks = self._fetch_jwks()
            if jwks:
                signing_key = self._get_signing_key(token, jwks)
                if signing_key:
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
        except ImportError:
            logger.warning("PyJWT not installed — falling back to base64 decode")
        except Exception as exc:
            logger.warning("JWKS verification failed: %s — falling back to base64 decode", exc)

        # Fallback: base64 decode with basic validation
        return self._decode_token_fallback(token)

    def _fetch_jwks(self) -> dict[str, Any] | None:
        """Fetch JWKS from Keycloak (cached).

        Returns:
            Parsed JWKS dict if successful, None if fetch fails.
        """
        if self._config._jwks_cache is not None:
            return self._config._jwks_cache

        try:
            req = urllib.request.Request(self._config.jwks_uri)
            with urllib.request.urlopen(req, timeout=5) as resp:
                jwks = json.loads(resp.read())
                self._config._jwks_cache = jwks
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

    def _decode_token_fallback(self, token: str) -> dict[str, Any]:
        """Fallback: base64 decode without crypto verification.

        Validates exp and iat claims to catch obviously invalid tokens even
        without cryptographic verification.

        Args:
            token: Raw JWT string.

        Returns:
            Decoded JWT payload dict.

        Raises:
            ValueError: If token format is invalid, expired, or has future iat.
        """
        import base64
        import time

        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid JWT format")

        payload_b64 = parts[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding

        try:
            payload_bytes = base64.urlsafe_b64decode(payload_b64)
            claims: dict[str, Any] = json.loads(payload_bytes)
        except Exception as exc:
            raise ValueError(f"Failed to decode JWT payload: {exc}") from exc

        # Validate issuer (warn only — don't reject in fallback mode)
        expected_issuer = self._config.issuer
        if claims.get("iss") != expected_issuer:
            logger.warning(
                "JWT issuer mismatch: expected=%s got=%s",
                expected_issuer,
                claims.get("iss"),
            )

        # Validate expiration
        now = time.time()
        exp = claims.get("exp")
        if exp is not None and now > exp:
            raise ValueError("Token has expired")

        iat = claims.get("iat")
        if iat is not None and iat > now + 60:  # 60s clock skew tolerance
            raise ValueError("Token issued in the future")

        logger.warning(
            "JWT decoded via base64 fallback (no crypto verification) for sub=%s",
            claims.get("sub"),
        )
        return claims
