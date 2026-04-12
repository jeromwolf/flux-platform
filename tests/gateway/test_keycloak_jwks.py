"""Tests for KeycloakMiddleware PyJWT + JWKS upgrade.

Covers JWKS fetching/caching, signing key extraction, and secure-only decode behavior.
The base64 fallback has been removed — these tests verify the new strict behavior.

TC-KJ02: _fetch_jwks caching and failure
TC-KJ03: _decode_token JWKS path — raises on JWKS unavailable (no fallback)
TC-KJ04: clear_jwks_cache
TC-KJ05: _get_signing_key kid matching
"""
from __future__ import annotations

import base64
import json
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from gateway.middleware.keycloak import KeycloakConfig, KeycloakMiddleware


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_token(
    payload: dict[str, Any],
    header: dict[str, Any] | None = None,
) -> str:
    """Build a syntactically valid JWT without crypto signing.

    The signature part is a dummy value — only the header and payload
    are actually used in tests.

    Args:
        payload: JWT claims dict.
        header: Optional JWT header dict (defaults to ``{"alg": "RS256", "typ": "JWT"}``).

    Returns:
        A dot-separated ``header.payload.signature`` string.
    """
    if header is None:
        header = {"alg": "RS256", "typ": "JWT"}

    def _b64(data: dict[str, Any]) -> str:
        raw = json.dumps(data).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    header_b64 = _b64(header)
    payload_b64 = _b64(payload)
    sig_b64 = base64.urlsafe_b64encode(b"fake-signature").rstrip(b"=").decode()
    return f"{header_b64}.{payload_b64}.{sig_b64}"


def _make_middleware(keycloak_url: str = "") -> KeycloakMiddleware:
    """Build a :class:`KeycloakMiddleware` wrapping a no-op ASGI app."""
    async def _dummy_app(scope, receive, send):  # pragma: no cover
        pass

    return KeycloakMiddleware(
        app=_dummy_app,
        keycloak_url=keycloak_url,
        realm="imsp",
        client_id="imsp-api",
    )


# ---------------------------------------------------------------------------
# TC-KJ02: _fetch_jwks caching and failure
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFetchJwks:
    """TC-KJ02: JWKS fetching, caching, and graceful failure."""

    def _fake_jwks_response(self, keys: list[dict[str, Any]]) -> MagicMock:
        """Return a mock context-manager response yielding JWKS JSON."""
        body = json.dumps({"keys": keys}).encode()
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=body)))
        cm.__exit__ = MagicMock(return_value=False)
        return cm

    # TC-KJ02a: second call returns cached data (urlopen called once)
    def test_fetch_jwks_caches_result(self):
        """_fetch_jwks returns the cached dict on the second call."""
        mw = _make_middleware(keycloak_url="http://keycloak:8080")
        fake_keys = [{"kid": "key-1", "kty": "RSA"}]

        with patch("urllib.request.urlopen", return_value=self._fake_jwks_response(fake_keys)) as mock_open:
            first = mw._fetch_jwks()
            second = mw._fetch_jwks()

        assert first is not None
        assert second is not None
        assert first is second  # same cached object
        mock_open.assert_called_once()  # only one real HTTP call

    # TC-KJ02b: unreachable JWKS URL returns None
    def test_fetch_jwks_failure_returns_none(self):
        """_fetch_jwks returns None when the JWKS endpoint is unreachable."""
        mw = _make_middleware(keycloak_url="http://keycloak:8080")

        with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
            result = mw._fetch_jwks()

        assert result is None

    # TC-KJ02c: fetched JWKS is stored on config
    def test_fetch_jwks_stores_on_config(self):
        """_fetch_jwks stores the parsed dict in _config._jwks_cache."""
        mw = _make_middleware(keycloak_url="http://keycloak:8080")
        fake_keys = [{"kid": "key-1", "kty": "RSA"}]

        with patch("urllib.request.urlopen", return_value=self._fake_jwks_response(fake_keys)):
            mw._fetch_jwks()

        assert mw._config._jwks_cache is not None
        assert mw._config._jwks_cache["keys"] == fake_keys

    # TC-KJ02d: pre-populated cache is returned without HTTP call
    def test_fetch_jwks_skips_http_when_cache_populated(self):
        """Pre-populated _jwks_cache is returned without making any HTTP call."""
        mw = _make_middleware(keycloak_url="http://keycloak:8080")
        existing = {"keys": [{"kid": "cached-key", "kty": "RSA"}]}
        mw._config._jwks_cache = existing
        mw._config._jwks_cached_at = time.time()

        with patch("urllib.request.urlopen") as mock_open:
            result = mw._fetch_jwks()

        mock_open.assert_not_called()
        assert result is existing


# ---------------------------------------------------------------------------
# TC-KJ05: JWKS cache TTL behavior
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestJwksCacheTTL:
    """TC-KJ05: JWKS cache TTL behavior."""

    # TC-KJ05a: fresh cache is returned without HTTP call
    def test_fresh_cache_skips_fetch(self):
        """Cache populated within TTL returns cached value without HTTP request."""
        mw = _make_middleware(keycloak_url="http://keycloak:8080")
        existing = {"keys": [{"kid": "k1", "kty": "RSA"}]}
        mw._config._jwks_cache = existing
        mw._config._jwks_cached_at = time.time()  # just now

        with patch("urllib.request.urlopen") as mock_open:
            result = mw._fetch_jwks()

        mock_open.assert_not_called()
        assert result is existing

    # TC-KJ05b: expired cache triggers re-fetch
    def test_expired_cache_triggers_refetch(self):
        """Cache older than TTL triggers new HTTP fetch."""
        mw = _make_middleware(keycloak_url="http://keycloak:8080")
        old_cache = {"keys": [{"kid": "old", "kty": "RSA"}]}
        mw._config._jwks_cache = old_cache
        mw._config._jwks_cached_at = time.time() - 3601  # expired

        new_jwks = {"keys": [{"kid": "new", "kty": "RSA"}]}
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(new_jwks).encode()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = mw._fetch_jwks()

        assert result == new_jwks
        assert mw._config._jwks_cache == new_jwks
        assert mw._config._jwks_cached_at > time.time() - 5  # recently updated

    # TC-KJ05c: clear_jwks_cache resets both cache and timestamp
    def test_clear_cache_resets_timestamp(self):
        """clear_jwks_cache resets _jwks_cache and _jwks_cached_at."""
        mw = _make_middleware(keycloak_url="http://keycloak:8080")
        mw._config._jwks_cache = {"keys": []}
        mw._config._jwks_cached_at = time.time()

        mw._config.clear_jwks_cache()

        assert mw._config._jwks_cache is None
        assert mw._config._jwks_cached_at == 0.0

    # TC-KJ05d: cache at exactly TTL boundary still valid
    def test_cache_at_ttl_boundary_still_valid(self):
        """Cache exactly at TTL - 1 second is still considered valid."""
        mw = _make_middleware(keycloak_url="http://keycloak:8080")
        existing = {"keys": [{"kid": "boundary", "kty": "RSA"}]}
        mw._config._jwks_cache = existing
        mw._config._jwks_cached_at = time.time() - 3599  # 1 second before expiry

        with patch("urllib.request.urlopen") as mock_open:
            result = mw._fetch_jwks()

        mock_open.assert_not_called()
        assert result is existing

    # TC-KJ05e: expired cache with fetch failure returns None
    def test_expired_cache_fetch_failure_returns_none(self):
        """When cache is expired and re-fetch fails, returns None."""
        mw = _make_middleware(keycloak_url="http://keycloak:8080")
        mw._config._jwks_cache = {"keys": []}
        mw._config._jwks_cached_at = time.time() - 7200  # long expired

        with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
            result = mw._fetch_jwks()

        assert result is None


# ---------------------------------------------------------------------------
# TC-KJ03: _decode_token — no fallback; raises ValueError on JWKS unavailable
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDecodeTokenNoFallback:
    """TC-KJ03: _decode_token raises ValueError when JWKS is unavailable (no base64 fallback)."""

    # TC-KJ03a: raises ValueError when JWKS fetch fails
    def test_decode_token_raises_on_jwks_failure(self):
        """When JWKS is unavailable, _decode_token raises ValueError (no fallback)."""
        now = int(time.time())
        payload = {
            "sub": "user-test",
            "iss": "http://keycloak:8080/realms/imsp",
            "exp": now + 3600,
            "iat": now - 5,
        }
        token = _make_fake_token(payload)
        mw = _make_middleware(keycloak_url="http://keycloak:8080")

        with patch("urllib.request.urlopen", side_effect=OSError("offline")):
            with pytest.raises(ValueError, match="[Ss]ervice unavailable"):
                mw._decode_token(token)

    # TC-KJ03b: raises ValueError when PyJWT is not installed
    def test_decode_token_raises_when_pyjwt_missing(self):
        """When PyJWT is not installed, _decode_token raises ValueError (no fallback)."""
        token = _make_fake_token({"sub": "user-test"})
        mw = _make_middleware(keycloak_url="http://keycloak:8080")

        with patch("builtins.__import__", side_effect=ImportError("No module named 'jwt'")):
            with pytest.raises((ValueError, ImportError)):
                mw._decode_token(token)

    # TC-KJ03c: raises ValueError when no matching signing key in JWKS
    def test_decode_token_raises_on_no_matching_key(self):
        """When JWKS has no matching key, _decode_token raises ValueError."""
        mw = _make_middleware(keycloak_url="http://keycloak:8080")
        fake_keys = [{"kid": "other-kid", "kty": "RSA"}]
        jwks = {"keys": fake_keys}
        mw._config._jwks_cache = jwks
        mw._config._jwks_cached_at = time.time()

        token = _make_fake_token({}, header={"alg": "RS256", "typ": "JWT", "kid": "missing-kid"})

        with patch("jwt.get_unverified_header", return_value={"kid": "missing-kid"}):
            with pytest.raises(ValueError, match="[Nn]o matching signing key|[Vv]erification failed"):
                mw._decode_token(token)


# ---------------------------------------------------------------------------
# TC-KJ04: clear_jwks_cache
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestClearJwksCache:
    """TC-KJ04: KeycloakConfig.clear_jwks_cache() method."""

    # TC-KJ04a: clearing None cache is a no-op
    def test_clear_jwks_cache_when_empty_is_noop(self):
        """Calling clear_jwks_cache when cache is None does not raise."""
        config = KeycloakConfig(keycloak_url="http://keycloak:8080", realm="imsp", client_id="imsp-api")
        assert config._jwks_cache is None
        config.clear_jwks_cache()  # must not raise
        assert config._jwks_cache is None

    # TC-KJ04b: populated cache is reset to None
    def test_clear_jwks_cache_resets_to_none(self):
        """After clear_jwks_cache, _jwks_cache is None."""
        config = KeycloakConfig(keycloak_url="http://keycloak:8080", realm="imsp", client_id="imsp-api")
        config._jwks_cache = {"keys": [{"kid": "k1"}]}

        config.clear_jwks_cache()

        assert config._jwks_cache is None

    # TC-KJ04c: fetch is retried after cache cleared
    def test_clear_jwks_cache_allows_refetch(self):
        """After clearing cache, _fetch_jwks makes a new HTTP call."""
        mw = _make_middleware(keycloak_url="http://keycloak:8080")
        fake_keys = [{"kid": "key-new", "kty": "RSA"}]
        body = json.dumps({"keys": fake_keys}).encode()
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=body)))
        cm.__exit__ = MagicMock(return_value=False)

        # Populate cache first
        mw._config._jwks_cache = {"keys": [{"kid": "key-old"}]}
        # Clear it
        mw._config.clear_jwks_cache()
        assert mw._config._jwks_cache is None

        # Now fetch should go to the network
        with patch("urllib.request.urlopen", return_value=cm) as mock_open:
            result = mw._fetch_jwks()

        mock_open.assert_called_once()
        assert result is not None
        assert result["keys"] == fake_keys


# ---------------------------------------------------------------------------
# TC-KJ06: _get_signing_key kid matching
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetSigningKey:
    """TC-KJ06: _get_signing_key returns None for unknown kid."""

    # TC-KJ06a: returns None when no key matches the token kid
    def test_get_signing_key_no_matching_kid(self):
        """Returns None when the JWKS contains no key for the token's kid."""
        mw = _make_middleware(keycloak_url="http://keycloak:8080")
        jwks = {"keys": [{"kid": "other-kid", "kty": "RSA", "n": "x", "e": "AQAB"}]}
        token = _make_fake_token({}, header={"alg": "RS256", "typ": "JWT", "kid": "missing-kid"})

        with patch("jwt.get_unverified_header", return_value={"kid": "missing-kid"}):
            result = mw._get_signing_key(token, jwks)

        assert result is None

    # TC-KJ06b: returns None when JWKS keys list is empty
    def test_get_signing_key_empty_jwks(self):
        """Returns None when the JWKS has no keys at all."""
        mw = _make_middleware(keycloak_url="http://keycloak:8080")
        jwks: dict[str, Any] = {"keys": []}
        token = _make_fake_token({}, header={"alg": "RS256", "typ": "JWT", "kid": "k1"})

        with patch("jwt.get_unverified_header", return_value={"kid": "k1"}):
            result = mw._get_signing_key(token, jwks)

        assert result is None

    # TC-KJ06c: returns None gracefully when header parse fails
    def test_get_signing_key_returns_none_on_header_error(self):
        """Returns None if JWT header parsing raises an exception."""
        mw = _make_middleware(keycloak_url="http://keycloak:8080")
        jwks = {"keys": [{"kid": "k1"}]}

        with patch("jwt.get_unverified_header", side_effect=Exception("bad header")):
            result = mw._get_signing_key("bad.token.here", jwks)

        assert result is None
