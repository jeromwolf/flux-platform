"""Tests for WebSocket auth security enhancements.

TC-WS01: WSAuthenticator warns when secret key is empty.
TC-WS02: WSAuthenticator rejects empty tokens.
TC-WS03: Dev-mode decode works for base64 and plain JSON tokens.
"""
from __future__ import annotations

import base64
import json
import logging

import pytest

from gateway.middleware.ws_auth import WSAuthConfig, WSAuthenticator


@pytest.mark.unit
class TestWSAuthSecurityWarning:
    """TC-WS01: Warning on empty secret key."""

    def test_ws01a_warns_when_secret_key_empty(self, caplog: pytest.LogCaptureFixture) -> None:
        """TC-WS01-a: authenticate() logs warning when secret_key is empty."""
        config = WSAuthConfig(require_auth=True, secret_key="")
        auth = WSAuthenticator(config)
        # Create a simple base64 token
        payload = base64.urlsafe_b64encode(json.dumps({"sub": "user1"}).encode()).decode()
        with caplog.at_level(logging.WARNING, logger="gateway.middleware.ws_auth"):
            try:
                auth.authenticate(payload)
            except ValueError:
                pass  # token format may vary
        # Check if PyJWT is available; warning only fires when jwt is importable
        try:
            import jwt  # noqa: F401
            assert any("no secret key configured" in r.message for r in caplog.records), \
                "Expected warning about empty secret key"
        except ImportError:
            pass  # No jwt, no warning expected

    def test_ws01b_no_warning_when_secret_key_set(self, caplog: pytest.LogCaptureFixture) -> None:
        """TC-WS01-b: No warning when secret_key is configured."""
        config = WSAuthConfig(require_auth=True, secret_key="my-secret")
        auth = WSAuthenticator(config)
        with caplog.at_level(logging.WARNING, logger="gateway.middleware.ws_auth"):
            try:
                auth.authenticate("invalid-token")
            except ValueError:
                pass  # Expected to fail on invalid token
        assert not any("no secret key configured" in r.message for r in caplog.records)


@pytest.mark.unit
class TestWSAuthTokenValidation:
    """TC-WS02: Token validation basics."""

    def test_ws02a_empty_token_raises(self) -> None:
        """TC-WS02-a: Empty token raises ValueError."""
        auth = WSAuthenticator(WSAuthConfig())
        with pytest.raises(ValueError, match="empty"):
            auth.authenticate("")

    def test_ws02b_dev_decode_plain_json(self) -> None:
        """TC-WS02-b: Dev decode handles plain JSON token."""
        auth = WSAuthenticator(WSAuthConfig(secret_key=""))
        token = json.dumps({"sub": "test-user", "role": "admin"})
        claims = auth._dev_decode(token)
        assert claims["sub"] == "test-user"
        assert claims["role"] == "admin"

    def test_ws02c_dev_decode_base64_token(self) -> None:
        """TC-WS02-c: Dev decode handles base64url-encoded JSON token."""
        auth = WSAuthenticator(WSAuthConfig(secret_key=""))
        payload = {"sub": "user-42"}
        b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        claims = auth._dev_decode(b64)
        assert claims["sub"] == "user-42"

    def test_ws02d_dev_decode_jwt_format(self) -> None:
        """TC-WS02-d: Dev decode handles 3-part JWT format (header.payload.sig)."""
        auth = WSAuthenticator(WSAuthConfig(secret_key=""))
        header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode()).decode().rstrip("=")
        payload = base64.urlsafe_b64encode(json.dumps({"sub": "jwt-user"}).encode()).decode().rstrip("=")
        token = f"{header}.{payload}.fake-signature"
        claims = auth._dev_decode(token)
        assert claims["sub"] == "jwt-user"

    def test_ws02e_extract_token_missing_param_raises(self) -> None:
        """TC-WS02-e: extract_token_from_query raises when param is missing."""
        auth = WSAuthenticator(WSAuthConfig())
        with pytest.raises(ValueError, match="Missing"):
            auth.extract_token_from_query("foo=bar")

    def test_ws02f_extract_token_empty_value_raises(self) -> None:
        """TC-WS02-f: extract_token_from_query raises on empty token value."""
        auth = WSAuthenticator(WSAuthConfig())
        with pytest.raises(ValueError, match="empty"):
            auth.extract_token_from_query("token=   ")

    def test_ws02g_config_from_env_defaults(self) -> None:
        """TC-WS02-g: WSAuthConfig.from_env produces correct defaults."""
        config = WSAuthConfig.from_env()
        assert config.require_auth is True
        assert config.token_param == "token"
