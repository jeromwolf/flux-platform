"""WebSocket authentication middleware."""
from __future__ import annotations

import json
import os
import urllib.parse
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WSAuthConfig:
    """WebSocket authentication configuration.

    Attributes:
        require_auth: Whether authentication is enforced for WS connections.
        token_param: URL query parameter name that carries the token.
        secret_key: Secret key used to verify JWT signatures.
    """

    require_auth: bool = True
    token_param: str = "token"
    secret_key: str = ""

    @classmethod
    def from_env(cls) -> WSAuthConfig:
        """Load configuration from environment variables.

        Environment variables:
            GATEWAY_WS_REQUIRE_AUTH: Enable auth enforcement (1/true/yes)
            GATEWAY_WS_TOKEN_PARAM: Query parameter name for the token
            GATEWAY_WS_SECRET_KEY: JWT secret key

        Returns:
            A :class:`WSAuthConfig` instance populated from environment.
        """
        require_raw = os.getenv("GATEWAY_WS_REQUIRE_AUTH", "true").lower()
        require_auth = require_raw in ("1", "true", "yes")

        return cls(
            require_auth=require_auth,
            token_param=os.getenv("GATEWAY_WS_TOKEN_PARAM", "token"),
            secret_key=os.getenv("GATEWAY_WS_SECRET_KEY", ""),
        )


class WSAuthenticator:
    """Authenticates WebSocket connections via query parameter token.

    Validates tokens using PyJWT when available, falling back to a
    simple base64-JSON decode for development environments.

    Args:
        config: Authentication configuration.
    """

    def __init__(self, config: WSAuthConfig) -> None:
        self._config = config

    @property
    def config(self) -> WSAuthConfig:
        """Return the authenticator configuration."""
        return self._config

    def authenticate(self, token: str) -> dict[str, Any]:
        """Validate a token and return user claims.

        Attempts JWT verification with PyJWT first. If PyJWT is not
        installed, falls back to a transparent base64-JSON decode so
        that tests and local development work without extra dependencies.

        Args:
            token: Raw token string extracted from the query parameter.

        Returns:
            Dictionary of user claims (e.g. ``{"sub": "user-id", ...}``).

        Raises:
            ValueError: If the token is empty, malformed, or signature
                verification fails.
        """
        if not token:
            raise ValueError("Token must not be empty")

        try:
            import jwt  # type: ignore[import]

            if not self._config.secret_key:
                # No secret key configured — fall back to dev mode decode.
                return self._dev_decode(token)
            try:
                claims: dict[str, Any] = jwt.decode(
                    token,
                    self._config.secret_key,
                    algorithms=["HS256"],
                )
                return claims
            except jwt.ExpiredSignatureError as exc:
                raise ValueError("Token has expired") from exc
            except jwt.InvalidTokenError as exc:
                raise ValueError(f"Invalid token: {exc}") from exc

        except ImportError:
            # PyJWT not installed — fall back to development-mode decode.
            return self._dev_decode(token)

    def _dev_decode(self, token: str) -> dict[str, Any]:
        """Decode a token without signature verification (dev/test only).

        Interprets the token as a base64url-encoded JSON payload, or as a
        plain JSON string, returning the decoded claims dict.

        Args:
            token: Raw token string.

        Returns:
            Dictionary of claims decoded from the token.

        Raises:
            ValueError: If the token cannot be decoded as JSON.
        """
        import base64

        # Attempt standard base64url decode of the payload portion.
        # Accept either a full 3-part JWT (header.payload.sig) or a raw
        # base64-encoded blob.
        parts = token.split(".")
        payload_b64 = parts[1] if len(parts) == 3 else parts[0]

        # Add padding if necessary.
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding

        try:
            decoded_bytes = base64.urlsafe_b64decode(payload_b64)
            claims: dict[str, Any] = json.loads(decoded_bytes)
            return claims
        except Exception:
            pass

        # Last resort: treat the whole token as a JSON string.
        try:
            claims = json.loads(token)
            if isinstance(claims, dict):
                return claims
        except json.JSONDecodeError:
            pass

        raise ValueError(
            f"Cannot decode token (PyJWT not installed and token is not "
            f"base64url-JSON or plain JSON): '{token[:20]}...'"
        )

    def extract_token_from_query(self, query_string: str) -> str:
        """Extract the authentication token from a URL query string.

        Args:
            query_string: Raw query string, e.g. ``"token=abc&foo=bar"``.
                Leading ``?`` is stripped automatically.

        Returns:
            The token value string.

        Raises:
            ValueError: If the expected query parameter is absent or empty.
        """
        qs = query_string.lstrip("?")
        params = urllib.parse.parse_qs(qs, keep_blank_values=False)
        values = params.get(self._config.token_param)
        if not values:
            raise ValueError(
                f"Missing required query parameter '{self._config.token_param}'"
            )
        token = values[0].strip()
        if not token:
            raise ValueError(
                f"Query parameter '{self._config.token_param}' is empty"
            )
        return token
