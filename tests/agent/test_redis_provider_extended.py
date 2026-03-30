"""Extended unit tests for agent/memory/redis_provider.py.

Covers the branches not exercised by test_redis_memory.py:
- Constructor: Redis available vs. fallback to FileMemoryProvider
- add(): stores JSON, trims, calls expire (TTL > 0)
- add(): no expire call when TTL = 0
- add(): delegates to fallback when Redis unavailable
- get_history(): returns deserialized MemoryEntry list
- get_history(): respects limit parameter
- get_history(): delegates to fallback
- clear(): calls delete on Redis key
- clear(): delegates to fallback
- list_sessions(): multi-page SCAN cursor pagination
- list_sessions(): deduplicates sessions
- list_sessions(): delegates to fallback
- _key(): returns correct prefixed key
- _entry_to_dict() / _dict_to_entry() roundtrip

All tests are @pytest.mark.unit and mock the Redis client throughout.
"""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch, call

import pytest

from agent.memory.models import MemoryEntry, MemoryType

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helper: build a pre-wired provider without touching real Redis
# ---------------------------------------------------------------------------


def _make_provider(
    prefix: str = "imsp:memory",
    max_messages: int = 10,
    session_ttl: int = 86400,
    mock_redis: MagicMock | None = None,
):
    """Return a RedisMemoryProvider with a mocked Redis client."""
    from agent.memory.redis_provider import RedisMemoryProvider

    provider = RedisMemoryProvider.__new__(RedisMemoryProvider)
    provider._prefix = prefix
    provider._max_messages = max_messages
    provider._session_ttl = session_ttl
    provider._redis = mock_redis if mock_redis is not None else MagicMock()
    provider._fallback = None
    return provider


def _make_fallback_provider():
    """Return a RedisMemoryProvider that fell back to FileMemoryProvider."""
    from agent.memory.redis_provider import RedisMemoryProvider
    from agent.memory.file_provider import FileMemoryProvider

    provider = RedisMemoryProvider.__new__(RedisMemoryProvider)
    provider._prefix = "imsp:memory"
    provider._max_messages = 10
    provider._session_ttl = 86400
    provider._redis = None
    provider._fallback = MagicMock(spec=FileMemoryProvider)
    return provider


# ---------------------------------------------------------------------------
# Constructor behavior
# ---------------------------------------------------------------------------


class TestRedisMemoryProviderConstructor:
    """RedisMemoryProvider.__init__ success and fallback paths."""

    def test_constructor_connects_to_redis_on_success(self):
        """When Redis responds to PING, _redis is set and _fallback is None."""
        from agent.memory.redis_provider import RedisMemoryProvider

        mock_client = MagicMock()
        mock_client.ping.return_value = True

        with patch("redis.from_url", return_value=mock_client) as mock_from_url:
            provider = RedisMemoryProvider(redis_url="redis://localhost:6379")

        mock_from_url.assert_called_once_with("redis://localhost:6379", decode_responses=True)
        assert provider._redis is mock_client
        assert provider._fallback is None

    def test_constructor_falls_back_on_connection_error(self):
        """When Redis is unavailable, _fallback is set and _redis is None."""
        from agent.memory.redis_provider import RedisMemoryProvider

        with patch("redis.from_url", side_effect=ConnectionError("refused")):
            provider = RedisMemoryProvider(redis_url="redis://localhost:6379")

        assert provider._redis is None
        assert provider._fallback is not None

    def test_constructor_falls_back_when_redis_import_missing(self):
        """When redis package is not installed, _fallback is used."""
        from agent.memory.redis_provider import RedisMemoryProvider

        with patch.dict("sys.modules", {"redis": None}):
            provider = RedisMemoryProvider(redis_url="redis://localhost:6379")

        assert provider._redis is None
        assert provider._fallback is not None

    def test_constructor_stores_config_params(self):
        """Constructor stores prefix, max_messages, session_ttl."""
        from agent.memory.redis_provider import RedisMemoryProvider

        mock_client = MagicMock()
        with patch("redis.from_url", return_value=mock_client):
            provider = RedisMemoryProvider(
                redis_url="redis://localhost:6379",
                max_messages=50,
                prefix="myapp:mem",
                session_ttl=3600,
            )

        assert provider._max_messages == 50
        assert provider._prefix == "myapp:mem"
        assert provider._session_ttl == 3600


# ---------------------------------------------------------------------------
# _key helper
# ---------------------------------------------------------------------------


class TestRedisMemoryProviderKey:
    """_key returns a correctly prefixed Redis key."""

    def test_key_format(self):
        """_key returns prefix:session_id."""
        provider = _make_provider(prefix="test:mem")
        assert provider._key("sess-1") == "test:mem:sess-1"

    def test_key_default_prefix(self):
        """Default prefix is 'imsp:memory'."""
        provider = _make_provider(prefix="imsp:memory")
        assert provider._key("abc") == "imsp:memory:abc"


# ---------------------------------------------------------------------------
# _entry_to_dict / _dict_to_entry roundtrip
# ---------------------------------------------------------------------------


class TestEntrySerialisation:
    """MemoryEntry serialization helpers."""

    def test_entry_to_dict_roundtrip(self):
        """_entry_to_dict and _dict_to_entry are inverses."""
        provider = _make_provider()
        entry = MemoryEntry(role=MemoryType.USER, content="hello", metadata={"k": "v"})
        d = provider._entry_to_dict(entry)
        restored = provider._dict_to_entry(d)

        assert restored.role == MemoryType.USER
        assert restored.content == "hello"
        assert restored.metadata == {"k": "v"}

    def test_entry_to_dict_uses_role_value(self):
        """_entry_to_dict stores role as the enum's string value."""
        provider = _make_provider()
        entry = MemoryEntry(role=MemoryType.ASSISTANT, content="hi")
        d = provider._entry_to_dict(entry)
        assert d["role"] == "assistant"


# ---------------------------------------------------------------------------
# add()
# ---------------------------------------------------------------------------


class TestRedisMemoryProviderAdd:
    """add() Redis path and fallback path."""

    def test_add_pushes_json_to_redis(self):
        """add() serializes entry to JSON and calls rpush."""
        mock_redis = MagicMock()
        provider = _make_provider(mock_redis=mock_redis)
        entry = MemoryEntry(role=MemoryType.USER, content="test message")

        provider.add(entry, session_id="s1")

        assert mock_redis.rpush.call_count == 1
        key_arg, json_arg = mock_redis.rpush.call_args[0]
        assert key_arg == "imsp:memory:s1"
        payload = json.loads(json_arg)
        assert payload["content"] == "test message"
        assert payload["role"] == "user"

    def test_add_trims_list(self):
        """add() calls ltrim to enforce max_messages limit."""
        mock_redis = MagicMock()
        provider = _make_provider(max_messages=5, mock_redis=mock_redis)
        entry = MemoryEntry(role=MemoryType.USER, content="msg")

        provider.add(entry, session_id="s1")

        mock_redis.ltrim.assert_called_once_with("imsp:memory:s1", -5, -1)

    def test_add_calls_expire_when_ttl_positive(self):
        """add() sets TTL via expire() when session_ttl > 0."""
        mock_redis = MagicMock()
        provider = _make_provider(session_ttl=1800, mock_redis=mock_redis)
        entry = MemoryEntry(role=MemoryType.ASSISTANT, content="resp")

        provider.add(entry, session_id="sess")

        mock_redis.expire.assert_called_once_with("imsp:memory:sess", 1800)

    def test_add_no_expire_when_ttl_zero(self):
        """add() does not call expire() when session_ttl is 0."""
        mock_redis = MagicMock()
        provider = _make_provider(session_ttl=0, mock_redis=mock_redis)
        entry = MemoryEntry(role=MemoryType.USER, content="msg")

        provider.add(entry, session_id="s1")

        mock_redis.expire.assert_not_called()

    def test_add_delegates_to_fallback(self):
        """add() calls fallback.add() when _fallback is set."""
        provider = _make_fallback_provider()
        entry = MemoryEntry(role=MemoryType.USER, content="msg")

        provider.add(entry, session_id="s2")

        provider._fallback.add.assert_called_once_with(entry, "s2")


# ---------------------------------------------------------------------------
# get_history()
# ---------------------------------------------------------------------------


class TestRedisMemoryProviderGetHistory:
    """get_history() deserialization and limit behavior."""

    def _make_raw_entry(self, role: str, content: str) -> str:
        return json.dumps({"role": role, "content": content, "metadata": {}})

    def test_get_history_returns_entries_in_order(self):
        """get_history() deserializes and returns entries oldest-first."""
        mock_redis = MagicMock()
        mock_redis.lrange.return_value = [
            self._make_raw_entry("user", "first"),
            self._make_raw_entry("assistant", "second"),
        ]
        provider = _make_provider(max_messages=10, mock_redis=mock_redis)

        entries = provider.get_history(session_id="s1")

        assert len(entries) == 2
        assert entries[0].role == MemoryType.USER
        assert entries[0].content == "first"
        assert entries[1].role == MemoryType.ASSISTANT
        assert entries[1].content == "second"

    def test_get_history_with_limit(self):
        """get_history() uses negative start index when limit is provided."""
        mock_redis = MagicMock()
        mock_redis.lrange.return_value = [self._make_raw_entry("user", "last3")]
        provider = _make_provider(max_messages=100, mock_redis=mock_redis)

        provider.get_history(session_id="s1", limit=3)

        mock_redis.lrange.assert_called_once_with("imsp:memory:s1", -3, -1)

    def test_get_history_empty_key_returns_empty_list(self):
        """get_history() returns [] when the Redis key has no entries."""
        mock_redis = MagicMock()
        mock_redis.lrange.return_value = []
        provider = _make_provider(mock_redis=mock_redis)

        result = provider.get_history(session_id="empty")

        assert result == []

    def test_get_history_delegates_to_fallback(self):
        """get_history() calls fallback.get_history() when _fallback is set."""
        provider = _make_fallback_provider()
        provider._fallback.get_history.return_value = []

        provider.get_history(session_id="s3", limit=5)

        provider._fallback.get_history.assert_called_once_with("s3", 5)


# ---------------------------------------------------------------------------
# clear()
# ---------------------------------------------------------------------------


class TestRedisMemoryProviderClear:
    """clear() deletes the Redis key."""

    def test_clear_deletes_key(self):
        """clear() calls redis.delete with the correct key."""
        mock_redis = MagicMock()
        provider = _make_provider(mock_redis=mock_redis)

        provider.clear(session_id="my-session")

        mock_redis.delete.assert_called_once_with("imsp:memory:my-session")

    def test_clear_delegates_to_fallback(self):
        """clear() calls fallback.clear() when _fallback is set."""
        provider = _make_fallback_provider()

        provider.clear(session_id="s4")

        provider._fallback.clear.assert_called_once_with("s4")


# ---------------------------------------------------------------------------
# list_sessions() — SCAN pagination and deduplication
# ---------------------------------------------------------------------------


class TestRedisMemoryProviderListSessions:
    """list_sessions() uses SCAN and handles pagination + deduplication."""

    def test_list_sessions_single_page(self):
        """list_sessions() terminates after a single SCAN returning cursor=0."""
        mock_redis = MagicMock()
        mock_redis.scan.return_value = (0, ["imsp:memory:alice", "imsp:memory:bob"])
        provider = _make_provider(prefix="imsp:memory", mock_redis=mock_redis)

        sessions = provider.list_sessions()

        assert sessions == ["alice", "bob"]
        assert mock_redis.scan.call_count == 1

    def test_list_sessions_multi_page_pagination(self):
        """list_sessions() loops until SCAN returns cursor 0."""
        mock_redis = MagicMock()
        # First page: cursor=42 (more pages), second page: cursor=0 (done)
        mock_redis.scan.side_effect = [
            (42, ["imsp:memory:alice"]),
            (0, ["imsp:memory:bob"]),
        ]
        provider = _make_provider(prefix="imsp:memory", mock_redis=mock_redis)

        sessions = provider.list_sessions()

        assert mock_redis.scan.call_count == 2
        assert "alice" in sessions
        assert "bob" in sessions

    def test_list_sessions_deduplicates(self):
        """list_sessions() returns each session ID at most once."""
        mock_redis = MagicMock()
        # Duplicate key returned across pages (edge case)
        mock_redis.scan.side_effect = [
            (7, ["imsp:memory:x", "imsp:memory:x"]),
            (0, ["imsp:memory:x"]),
        ]
        provider = _make_provider(prefix="imsp:memory", mock_redis=mock_redis)

        sessions = provider.list_sessions()

        assert sessions.count("x") == 1

    def test_list_sessions_sorted(self):
        """list_sessions() returns session IDs in sorted order."""
        mock_redis = MagicMock()
        mock_redis.scan.return_value = (0, ["imsp:memory:charlie", "imsp:memory:alice", "imsp:memory:bob"])
        provider = _make_provider(prefix="imsp:memory", mock_redis=mock_redis)

        sessions = provider.list_sessions()

        assert sessions == sorted(sessions)

    def test_list_sessions_empty(self):
        """list_sessions() returns [] when no sessions exist."""
        mock_redis = MagicMock()
        mock_redis.scan.return_value = (0, [])
        provider = _make_provider(mock_redis=mock_redis)

        sessions = provider.list_sessions()

        assert sessions == []

    def test_list_sessions_delegates_to_fallback(self):
        """list_sessions() calls fallback.list_sessions() when _fallback is set."""
        provider = _make_fallback_provider()
        provider._fallback.list_sessions.return_value = ["s1"]

        result = provider.list_sessions()

        provider._fallback.list_sessions.assert_called_once()
        assert result == ["s1"]
