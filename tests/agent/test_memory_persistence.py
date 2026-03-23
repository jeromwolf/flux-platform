"""Tests for persistent memory providers and factory.

Covers:
    TestFileMemoryProvider  — file-based persistence (tmp_path)
    TestRedisMemoryProvider — Redis provider with fallback path
    TestMemoryFactory       — factory routing and default config
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from agent.memory.buffer import BufferMemory
from agent.memory.factory import MemoryConfig, create_memory_provider
from agent.memory.file_provider import FileMemoryProvider
from agent.memory.models import MemoryEntry, MemoryType
from agent.memory.redis_provider import RedisMemoryProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entry(role: MemoryType, content: str) -> MemoryEntry:
    return MemoryEntry(role=role, content=content)


# ===========================================================================
# FileMemoryProvider
# ===========================================================================


class TestFileMemoryProvider:
    """TC-FMP01 – TC-FMP07: File-based memory provider."""

    # TC-FMP01 -----------------------------------------------------------------
    def test_add_and_retrieve(self, tmp_path: Path) -> None:
        """Added entries are retrievable in insertion order."""
        provider = FileMemoryProvider(storage_dir=str(tmp_path))

        provider.add(_entry(MemoryType.USER, "hello"), session_id="s1")
        provider.add(_entry(MemoryType.ASSISTANT, "hi there"), session_id="s1")

        history = provider.get_history("s1")
        assert len(history) == 2
        assert history[0].role == MemoryType.USER
        assert history[0].content == "hello"
        assert history[1].role == MemoryType.ASSISTANT
        assert history[1].content == "hi there"

    # TC-FMP02 -----------------------------------------------------------------
    def test_persistence_across_instances(self, tmp_path: Path) -> None:
        """Data written by one instance is readable by a fresh instance."""
        provider1 = FileMemoryProvider(storage_dir=str(tmp_path))
        provider1.add(_entry(MemoryType.USER, "persistent message"), session_id="s1")

        # New instance — no in-memory cache
        provider2 = FileMemoryProvider(storage_dir=str(tmp_path))
        history = provider2.get_history("s1")

        assert len(history) == 1
        assert history[0].content == "persistent message"
        assert history[0].role == MemoryType.USER

    # TC-FMP03 -----------------------------------------------------------------
    def test_max_messages_truncation(self, tmp_path: Path) -> None:
        """Only the most-recent *max_messages* entries are retained."""
        provider = FileMemoryProvider(storage_dir=str(tmp_path), max_messages=3)

        for i in range(5):
            provider.add(_entry(MemoryType.USER, f"msg{i}"), session_id="s1")

        history = provider.get_history("s1")
        assert len(history) == 3
        # Should keep the last 3 (msg2, msg3, msg4)
        assert history[0].content == "msg2"
        assert history[-1].content == "msg4"

    # TC-FMP04 -----------------------------------------------------------------
    def test_clear_removes_file(self, tmp_path: Path) -> None:
        """clear() removes both in-memory cache and the JSON file."""
        provider = FileMemoryProvider(storage_dir=str(tmp_path))
        provider.add(_entry(MemoryType.USER, "to be deleted"), session_id="s1")

        session_file = tmp_path / "s1.json"
        assert session_file.exists()

        provider.clear("s1")

        assert not session_file.exists()
        assert provider.get_history("s1") == []

    # TC-FMP05 -----------------------------------------------------------------
    def test_list_sessions(self, tmp_path: Path) -> None:
        """list_sessions() returns all session IDs with persisted files."""
        provider = FileMemoryProvider(storage_dir=str(tmp_path))
        provider.add(_entry(MemoryType.USER, "a"), session_id="alice")
        provider.add(_entry(MemoryType.USER, "b"), session_id="bob")

        sessions = provider.list_sessions()
        assert set(sessions) == {"alice", "bob"}
        assert sessions == sorted(sessions)  # sorted order

    # TC-FMP06 -----------------------------------------------------------------
    def test_session_isolation(self, tmp_path: Path) -> None:
        """Entries added to one session do not appear in another."""
        provider = FileMemoryProvider(storage_dir=str(tmp_path))
        provider.add(_entry(MemoryType.USER, "for alice"), session_id="alice")
        provider.add(_entry(MemoryType.ASSISTANT, "for bob"), session_id="bob")

        assert len(provider.get_history("alice")) == 1
        assert provider.get_history("alice")[0].content == "for alice"
        assert len(provider.get_history("bob")) == 1
        assert provider.get_history("bob")[0].content == "for bob"

    # TC-FMP07 -----------------------------------------------------------------
    def test_safe_session_id(self, tmp_path: Path) -> None:
        """Path-traversal characters in session_id are sanitised."""
        provider = FileMemoryProvider(storage_dir=str(tmp_path))
        dangerous_id = "../../etc/passwd"

        provider.add(_entry(MemoryType.USER, "attack"), session_id=dangerous_id)

        # The resulting file must live inside tmp_path, not outside it
        safe_id = dangerous_id.replace("/", "_").replace("..", "_")
        expected_file = tmp_path / f"{safe_id}.json"
        assert expected_file.exists()

        # No file should have been written outside the storage directory
        resolved = expected_file.resolve()
        assert str(resolved).startswith(str(tmp_path.resolve()))

    # TC-FMP08 -----------------------------------------------------------------
    def test_get_history_limit(self, tmp_path: Path) -> None:
        """get_history(limit=N) returns at most N most-recent entries."""
        provider = FileMemoryProvider(storage_dir=str(tmp_path))
        for i in range(10):
            provider.add(_entry(MemoryType.USER, f"m{i}"), session_id="s")

        recent = provider.get_history("s", limit=3)
        assert len(recent) == 3
        assert recent[-1].content == "m9"

    # TC-FMP09 -----------------------------------------------------------------
    def test_empty_session_returns_empty_list(self, tmp_path: Path) -> None:
        """get_history for an unknown session returns []."""
        provider = FileMemoryProvider(storage_dir=str(tmp_path))
        assert provider.get_history("nonexistent") == []

    # TC-FMP10 -----------------------------------------------------------------
    def test_metadata_roundtrip(self, tmp_path: Path) -> None:
        """Custom metadata is preserved through serialisation/deserialisation."""
        provider = FileMemoryProvider(storage_dir=str(tmp_path))
        entry = MemoryEntry(
            role=MemoryType.SYSTEM,
            content="sys msg",
            metadata={"source": "test", "priority": 1},
        )
        provider.add(entry, session_id="meta_test")

        fresh = FileMemoryProvider(storage_dir=str(tmp_path))
        history = fresh.get_history("meta_test")
        assert history[0].metadata == {"source": "test", "priority": 1}


# ===========================================================================
# RedisMemoryProvider
# ===========================================================================


class TestRedisMemoryProvider:
    """TC-RMP01 – TC-RMP02: Redis provider (fallback path only in unit tests)."""

    # TC-RMP01 -----------------------------------------------------------------
    def test_fallback_to_file_when_redis_unavailable(self, tmp_path: Path) -> None:
        """When Redis is unreachable, the provider falls back silently."""
        provider = RedisMemoryProvider(
            redis_url="redis://localhost:19999",  # nothing running there
            max_messages=50,
        )
        # Fallback attribute must be set
        assert provider._fallback is not None

    # TC-RMP02 -----------------------------------------------------------------
    def test_fallback_add_and_retrieve(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Fallback provider correctly stores and retrieves entries."""
        from agent.memory.file_provider import FileMemoryProvider

        # Force fallback by pointing at a port guaranteed to be closed
        provider = RedisMemoryProvider(
            redis_url="redis://localhost:19999",
            max_messages=100,
        )
        # Redirect fallback storage to tmp_path for test isolation
        provider._fallback = FileMemoryProvider(
            storage_dir=str(tmp_path), max_messages=100
        )

        provider.add(_entry(MemoryType.USER, "fallback msg"), session_id="fb")
        history = provider.get_history("fb")
        assert len(history) == 1
        assert history[0].content == "fallback msg"

    # TC-RMP03 -----------------------------------------------------------------
    def test_fallback_clear(self, tmp_path: Path) -> None:
        """clear() is forwarded to fallback provider."""
        from agent.memory.file_provider import FileMemoryProvider

        provider = RedisMemoryProvider(redis_url="redis://localhost:19999")
        provider._fallback = FileMemoryProvider(storage_dir=str(tmp_path))

        provider.add(_entry(MemoryType.ASSISTANT, "to clear"), session_id="clr")
        provider.clear("clr")
        assert provider.get_history("clr") == []

    # TC-RMP04 -----------------------------------------------------------------
    def test_fallback_list_sessions(self, tmp_path: Path) -> None:
        """list_sessions() is forwarded to fallback provider."""
        from agent.memory.file_provider import FileMemoryProvider

        provider = RedisMemoryProvider(redis_url="redis://localhost:19999")
        provider._fallback = FileMemoryProvider(storage_dir=str(tmp_path))

        provider.add(_entry(MemoryType.USER, "x"), session_id="sa")
        provider.add(_entry(MemoryType.USER, "y"), session_id="sb")

        sessions = provider.list_sessions()
        assert set(sessions) == {"sa", "sb"}


# ===========================================================================
# MemoryFactory
# ===========================================================================


class TestMemoryFactory:
    """TC-MF01 – TC-MF04: Factory routing and config defaults."""

    # TC-MF01 -----------------------------------------------------------------
    def test_create_buffer_provider(self) -> None:
        """MemoryConfig(backend='buffer') returns a BufferMemory instance."""
        cfg = MemoryConfig(backend="buffer", max_messages=42)
        provider = create_memory_provider(cfg)
        assert isinstance(provider, BufferMemory)

    # TC-MF02 -----------------------------------------------------------------
    def test_create_file_provider(self, tmp_path: Path) -> None:
        """MemoryConfig(backend='file') returns a FileMemoryProvider instance."""
        cfg = MemoryConfig(backend="file", storage_dir=str(tmp_path))
        provider = create_memory_provider(cfg)
        assert isinstance(provider, FileMemoryProvider)

    # TC-MF03 -----------------------------------------------------------------
    def test_create_redis_falls_back(self) -> None:
        """MemoryConfig(backend='redis') with no Redis returns a provider
        that falls back gracefully (either Redis or FileMemoryProvider)."""
        cfg = MemoryConfig(backend="redis", redis_url="redis://localhost:19999")
        provider = create_memory_provider(cfg)
        assert isinstance(provider, RedisMemoryProvider)
        # When Redis is unavailable, fallback must be set
        assert provider._fallback is not None

    # TC-MF04 -----------------------------------------------------------------
    def test_default_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """create_memory_provider(None) reads MEMORY_BACKEND env var."""
        monkeypatch.delenv("MEMORY_BACKEND", raising=False)
        provider = create_memory_provider(None)
        # Default backend is "file"
        assert isinstance(provider, FileMemoryProvider)

    # TC-MF05 -----------------------------------------------------------------
    def test_env_backend_buffer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """MEMORY_BACKEND=buffer produces a BufferMemory."""
        monkeypatch.setenv("MEMORY_BACKEND", "buffer")
        provider = create_memory_provider(None)
        assert isinstance(provider, BufferMemory)

    # TC-MF06 -----------------------------------------------------------------
    def test_env_backend_redis(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """MEMORY_BACKEND=redis produces a RedisMemoryProvider (with fallback)."""
        monkeypatch.setenv("MEMORY_BACKEND", "redis")
        provider = create_memory_provider(None)
        assert isinstance(provider, RedisMemoryProvider)
