"""Tests for RedisMemoryProvider improvements."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from agent.memory.models import MemoryEntry, MemoryType

pytestmark = pytest.mark.unit


class TestRedisMemoryProviderTTL:
    """Test session TTL and SCAN improvements."""

    def test_add_sets_ttl_on_key(self):
        """add() calls expire() after rpush when session_ttl > 0."""
        mock_redis = MagicMock()

        from agent.memory.redis_provider import RedisMemoryProvider

        provider = RedisMemoryProvider.__new__(RedisMemoryProvider)
        provider._max_messages = 100
        provider._prefix = "test"
        provider._session_ttl = 3600
        provider._redis = mock_redis
        provider._fallback = None

        entry = MemoryEntry(role=MemoryType.USER, content="hello")
        provider.add(entry, session_id="s1")

        mock_redis.rpush.assert_called_once()
        mock_redis.ltrim.assert_called_once()
        mock_redis.expire.assert_called_once_with("test:s1", 3600)

    def test_add_skips_ttl_when_zero(self):
        """add() does not call expire() when session_ttl is 0."""
        mock_redis = MagicMock()

        from agent.memory.redis_provider import RedisMemoryProvider

        provider = RedisMemoryProvider.__new__(RedisMemoryProvider)
        provider._max_messages = 100
        provider._prefix = "test"
        provider._session_ttl = 0
        provider._redis = mock_redis
        provider._fallback = None

        entry = MemoryEntry(role=MemoryType.USER, content="hello")
        provider.add(entry, session_id="s1")

        mock_redis.expire.assert_not_called()

    def test_list_sessions_uses_scan(self):
        """list_sessions() uses SCAN instead of KEYS."""
        mock_redis = MagicMock()
        mock_redis.scan.return_value = (0, ["test:s1", "test:s2"])

        from agent.memory.redis_provider import RedisMemoryProvider

        provider = RedisMemoryProvider.__new__(RedisMemoryProvider)
        provider._prefix = "test"
        provider._redis = mock_redis
        provider._fallback = None

        sessions = provider.list_sessions()

        mock_redis.scan.assert_called()
        mock_redis.keys.assert_not_called()
        assert sessions == ["s1", "s2"]


class TestRedisMemoryProviderFromEnv:
    """Test from_env() classmethod."""

    def test_from_env_defaults(self):
        """from_env() uses default values when env vars not set."""
        with patch.dict(os.environ, {}, clear=True), patch(
            "agent.memory.redis_provider.RedisMemoryProvider.__init__",
            return_value=None,
        ) as mock_init:
            from agent.memory.redis_provider import RedisMemoryProvider

            RedisMemoryProvider.from_env()
            mock_init.assert_called_once_with(
                redis_url="redis://localhost:6379",
                max_messages=100,
                prefix="imsp:memory",
                session_ttl=86400,
            )

    def test_from_env_custom(self):
        """from_env() reads custom values from env vars."""
        env = {
            "AGENT_MEMORY_REDIS_URL": "redis://custom:6380",
            "AGENT_MEMORY_MAX_MESSAGES": "50",
            "AGENT_MEMORY_PREFIX": "custom",
            "AGENT_MEMORY_SESSION_TTL": "7200",
        }
        with patch.dict(os.environ, env, clear=True), patch(
            "agent.memory.redis_provider.RedisMemoryProvider.__init__",
            return_value=None,
        ) as mock_init:
            from agent.memory.redis_provider import RedisMemoryProvider

            RedisMemoryProvider.from_env()
            mock_init.assert_called_once_with(
                redis_url="redis://custom:6380",
                max_messages=50,
                prefix="custom",
                session_ttl=7200,
            )
