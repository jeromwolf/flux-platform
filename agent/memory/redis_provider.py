"""Redis-backed persistent memory provider with automatic fallback."""
from __future__ import annotations

import json

from agent.memory.models import MemoryEntry, MemoryType


class RedisMemoryProvider:
    """Redis-backed memory with automatic fallback to :class:`FileMemoryProvider`.

    On instantiation the provider attempts to connect to Redis and verifies
    reachability with a ``PING``.  If Redis is unavailable (import error,
    connection refused, etc.) the provider transparently delegates every
    operation to a :class:`FileMemoryProvider` instance stored under the
    same *max_messages* budget.

    Args:
        redis_url: Redis connection URL, e.g. ``"redis://localhost:6379"``.
        max_messages: Maximum messages to retain per session list.
        prefix: Key prefix used to namespace sessions in Redis.
        session_ttl: Session TTL in seconds (0 = no expiration, default: 86400 = 24 hours).
    """

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        max_messages: int = 100,
        prefix: str = "imsp:memory",
        session_ttl: int = 86400,
    ) -> None:
        self._max_messages = max_messages
        self._prefix = prefix
        self._session_ttl = session_ttl
        self._redis = None
        self._fallback = None

        try:
            import redis  # type: ignore[import]

            client = redis.from_url(redis_url, decode_responses=True)
            client.ping()
            self._redis = client
        except Exception:
            from agent.memory.file_provider import FileMemoryProvider

            self._fallback = FileMemoryProvider(max_messages=max_messages)

    @classmethod
    def from_env(cls) -> RedisMemoryProvider:
        """Create provider from ``AGENT_MEMORY_*`` environment variables.

        Environment variables:
            AGENT_MEMORY_REDIS_URL: Redis connection URL (default: redis://localhost:6379).
            AGENT_MEMORY_MAX_MESSAGES: Max messages per session (default: 100).
            AGENT_MEMORY_PREFIX: Key prefix (default: imsp:memory).
            AGENT_MEMORY_SESSION_TTL: Session TTL in seconds (default: 86400).

        Returns:
            A :class:`RedisMemoryProvider` instance.
        """
        import os

        return cls(
            redis_url=os.environ.get("AGENT_MEMORY_REDIS_URL", "redis://localhost:6379"),
            max_messages=int(os.environ.get("AGENT_MEMORY_MAX_MESSAGES", "100")),
            prefix=os.environ.get("AGENT_MEMORY_PREFIX", "imsp:memory"),
            session_ttl=int(os.environ.get("AGENT_MEMORY_SESSION_TTL", "86400")),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _key(self, session_id: str) -> str:
        return f"{self._prefix}:{session_id}"

    def _entry_to_dict(self, entry: MemoryEntry) -> dict:
        return {
            "role": entry.role.value if isinstance(entry.role, MemoryType) else str(entry.role),
            "content": entry.content,
            "metadata": entry.metadata,
        }

    def _dict_to_entry(self, d: dict) -> MemoryEntry:
        return MemoryEntry(
            role=MemoryType(d["role"]),
            content=d["content"],
            metadata=d.get("metadata", {}),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, entry: MemoryEntry, session_id: str = "default") -> None:
        """Append *entry* to the Redis list for *session_id*.

        Trims the list to keep at most *max_messages* entries.
        Falls back to :class:`FileMemoryProvider` if Redis is unavailable.

        Args:
            entry: The :class:`MemoryEntry` to store.
            session_id: Identifier for the conversation session.
        """
        if self._fallback is not None:
            return self._fallback.add(entry, session_id)

        data = json.dumps(self._entry_to_dict(entry), ensure_ascii=False)
        key = self._key(session_id)
        self._redis.rpush(key, data)
        self._redis.ltrim(key, -self._max_messages, -1)
        if self._session_ttl > 0:
            self._redis.expire(key, self._session_ttl)

    def get_history(
        self,
        session_id: str = "default",
        limit: int | None = None,
    ) -> list[MemoryEntry]:
        """Return stored entries for *session_id*.

        Args:
            session_id: The session to retrieve.
            limit: If given, return only the *limit* most-recent entries.

        Returns:
            List of :class:`MemoryEntry` objects (oldest-first).
        """
        if self._fallback is not None:
            return self._fallback.get_history(session_id, limit)

        key = self._key(session_id)
        start = -(limit or self._max_messages)
        items = self._redis.lrange(key, start, -1)
        return [self._dict_to_entry(json.loads(raw)) for raw in items]

    def clear(self, session_id: str = "default") -> None:
        """Delete all messages for *session_id*.

        Args:
            session_id: The session to clear.
        """
        if self._fallback is not None:
            return self._fallback.clear(session_id)
        self._redis.delete(self._key(session_id))

    def list_sessions(self) -> list[str]:
        """Return sorted list of all known session IDs.

        Uses ``SCAN`` instead of ``KEYS`` to avoid blocking Redis
        in production environments with large key spaces.

        Returns:
            Sorted list of session identifier strings.
        """
        if self._fallback is not None:
            return self._fallback.list_sessions()

        prefix_len = len(self._prefix) + 1  # +1 for the ":"
        sessions: list[str] = []
        cursor = 0
        while True:
            cursor, keys = self._redis.scan(cursor, match=f"{self._prefix}:*", count=100)
            sessions.extend(k[prefix_len:] for k in keys)
            if cursor == 0:
                break
        return sorted(set(sessions))
