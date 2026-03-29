"""Tests for FileMemoryProvider and memory factory.

Covers:
    TestFileMemoryProvider  — file-based persistence (10 TCs)
    TestMemoryConfig        — dataclass defaults and immutability (3 TCs)
    TestCreateMemoryProvider — factory routing, env-var override (6 TCs)
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from agent.memory.buffer import BufferMemory
from agent.memory.factory import MemoryConfig, create_memory_provider
from agent.memory.file_provider import FileMemoryProvider
from agent.memory.models import MemoryEntry, MemoryType
from agent.memory.redis_provider import RedisMemoryProvider

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _entry(role: MemoryType = MemoryType.USER, content: str = "hello") -> MemoryEntry:
    return MemoryEntry(role=role, content=content)


# ===========================================================================
# TestFileMemoryProvider
# ===========================================================================


class TestFileMemoryProvider:
    """TC-FMPF-01 – TC-FMPF-10: FileMemoryProvider behaviour."""

    # TC-FMPF-01 ---------------------------------------------------------------
    @pytest.mark.unit
    def test_init_creates_directory(self, tmp_path: Path) -> None:
        """Constructor creates the storage_dir when it does not exist."""
        new_dir = tmp_path / "nested" / "sessions"
        assert not new_dir.exists()

        FileMemoryProvider(storage_dir=str(new_dir))

        assert new_dir.is_dir()

    # TC-FMPF-02 ---------------------------------------------------------------
    @pytest.mark.unit
    def test_add_and_get_history(self, tmp_path: Path) -> None:
        """Entries added via add() are returned by get_history() in order."""
        provider = FileMemoryProvider(storage_dir=str(tmp_path))

        provider.add(_entry(MemoryType.USER, "first"), session_id="s1")
        provider.add(_entry(MemoryType.ASSISTANT, "second"), session_id="s1")

        history = provider.get_history("s1")
        assert len(history) == 2
        assert history[0].role == MemoryType.USER
        assert history[0].content == "first"
        assert history[1].role == MemoryType.ASSISTANT
        assert history[1].content == "second"

    # TC-FMPF-03 ---------------------------------------------------------------
    @pytest.mark.unit
    def test_add_persists_to_disk(self, tmp_path: Path) -> None:
        """Data written by one instance is readable by a fresh instance."""
        provider1 = FileMemoryProvider(storage_dir=str(tmp_path))
        provider1.add(_entry(MemoryType.USER, "persistent"), session_id="p1")

        # Fresh instance — no in-memory cache
        provider2 = FileMemoryProvider(storage_dir=str(tmp_path))
        history = provider2.get_history("p1")

        assert len(history) == 1
        assert history[0].content == "persistent"
        assert history[0].role == MemoryType.USER

    # TC-FMPF-04 ---------------------------------------------------------------
    @pytest.mark.unit
    def test_max_messages_eviction(self, tmp_path: Path) -> None:
        """Adding more than max_messages entries evicts the oldest ones."""
        provider = FileMemoryProvider(storage_dir=str(tmp_path), max_messages=3)

        for i in range(5):
            provider.add(_entry(content=f"msg{i}"), session_id="s1")

        history = provider.get_history("s1")
        assert len(history) == 3
        assert history[0].content == "msg2"
        assert history[1].content == "msg3"
        assert history[2].content == "msg4"

    # TC-FMPF-05 ---------------------------------------------------------------
    @pytest.mark.unit
    def test_get_history_with_limit(self, tmp_path: Path) -> None:
        """get_history(limit=N) returns the N most-recent entries."""
        provider = FileMemoryProvider(storage_dir=str(tmp_path))
        for i in range(5):
            provider.add(_entry(content=f"m{i}"), session_id="s")

        recent = provider.get_history("s", limit=2)
        assert len(recent) == 2
        assert recent[0].content == "m3"
        assert recent[1].content == "m4"

    # TC-FMPF-06 ---------------------------------------------------------------
    @pytest.mark.unit
    def test_get_history_empty_session(self, tmp_path: Path) -> None:
        """get_history for an unknown session returns an empty list."""
        provider = FileMemoryProvider(storage_dir=str(tmp_path))
        assert provider.get_history("nonexistent") == []

    # TC-FMPF-07 ---------------------------------------------------------------
    @pytest.mark.unit
    def test_clear_removes_cache_and_file(self, tmp_path: Path) -> None:
        """clear() removes both the in-memory cache and the JSON file."""
        provider = FileMemoryProvider(storage_dir=str(tmp_path))
        provider.add(_entry(content="to delete"), session_id="del_me")

        session_file = tmp_path / "del_me.json"
        assert session_file.exists()

        provider.clear("del_me")

        assert not session_file.exists()
        assert provider.get_history("del_me") == []

    # TC-FMPF-08 ---------------------------------------------------------------
    @pytest.mark.unit
    def test_list_sessions(self, tmp_path: Path) -> None:
        """list_sessions() returns a sorted list of all persisted session IDs."""
        provider = FileMemoryProvider(storage_dir=str(tmp_path))
        provider.add(_entry(content="a"), session_id="charlie")
        provider.add(_entry(content="b"), session_id="alpha")
        provider.add(_entry(content="c"), session_id="bravo")

        sessions = provider.list_sessions()
        assert sessions == ["alpha", "bravo", "charlie"]

    # TC-FMPF-09 ---------------------------------------------------------------
    @pytest.mark.unit
    def test_session_path_sanitizes(self, tmp_path: Path) -> None:
        """'/' in session_id is replaced by '_' and '..' by '_'."""
        provider = FileMemoryProvider(storage_dir=str(tmp_path))

        slash_path = provider._session_path("a/b")
        assert slash_path.name == "a_b.json"
        assert slash_path.parent == tmp_path

        dotdot_path = provider._session_path("../etc/passwd")
        assert ".." not in dotdot_path.name
        # The file must live inside storage_dir
        assert dotdot_path.parent == tmp_path

    # TC-FMPF-10 ---------------------------------------------------------------
    @pytest.mark.unit
    def test_load_session_caches(self, tmp_path: Path) -> None:
        """A second call to _load_session returns the cached object without
        re-reading the file."""
        provider = FileMemoryProvider(storage_dir=str(tmp_path))
        provider.add(_entry(content="cached"), session_id="cx")

        # Warm the cache via get_history
        first = provider.get_history("cx")

        # Corrupt the file on disk — cache should still return stale data
        session_file = tmp_path / "cx.json"
        session_file.write_text("[]", encoding="utf-8")

        second = provider.get_history("cx")

        # Cache hit: returns the in-memory list, not the empty file
        assert second == first
        assert len(second) == 1
        assert second[0].content == "cached"


# ===========================================================================
# TestMemoryConfig
# ===========================================================================


class TestMemoryConfig:
    """TC-MCFG-01 – TC-MCFG-03: MemoryConfig dataclass."""

    # TC-MCFG-01 ---------------------------------------------------------------
    @pytest.mark.unit
    def test_defaults(self) -> None:
        """Default field values match specification."""
        cfg = MemoryConfig()
        assert cfg.backend == "file"
        assert cfg.max_messages == 100
        assert cfg.storage_dir == ".imsp/memory"
        assert cfg.redis_url == "redis://localhost:6379"

    # TC-MCFG-02 ---------------------------------------------------------------
    @pytest.mark.unit
    def test_frozen(self) -> None:
        """MemoryConfig is immutable; attribute assignment raises FrozenInstanceError."""
        cfg = MemoryConfig()
        with pytest.raises((AttributeError, TypeError)):
            cfg.backend = "redis"  # type: ignore[misc]

    # TC-MCFG-03 ---------------------------------------------------------------
    @pytest.mark.unit
    def test_custom_values(self) -> None:
        """All fields can be set at construction time."""
        cfg = MemoryConfig(
            backend="redis",
            max_messages=50,
            storage_dir="/tmp/custom",
            redis_url="redis://myhost:6380",
        )
        assert cfg.backend == "redis"
        assert cfg.max_messages == 50
        assert cfg.storage_dir == "/tmp/custom"
        assert cfg.redis_url == "redis://myhost:6380"


# ===========================================================================
# TestCreateMemoryProvider
# ===========================================================================


class TestCreateMemoryProvider:
    """TC-CMP-01 – TC-CMP-06: create_memory_provider() routing."""

    # TC-CMP-01 ----------------------------------------------------------------
    @pytest.mark.unit
    def test_default_returns_file_provider(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With no config and no env var the factory returns FileMemoryProvider."""
        monkeypatch.delenv("MEMORY_BACKEND", raising=False)
        provider = create_memory_provider(None)
        assert isinstance(provider, FileMemoryProvider)

    # TC-CMP-02 ----------------------------------------------------------------
    @pytest.mark.unit
    def test_buffer_backend(self) -> None:
        """MemoryConfig(backend='buffer') returns BufferMemory."""
        cfg = MemoryConfig(backend="buffer")
        provider = create_memory_provider(cfg)
        assert isinstance(provider, BufferMemory)

    # TC-CMP-03 ----------------------------------------------------------------
    @pytest.mark.unit
    def test_file_backend(self, tmp_path: Path) -> None:
        """MemoryConfig(backend='file') returns FileMemoryProvider."""
        cfg = MemoryConfig(backend="file", storage_dir=str(tmp_path))
        provider = create_memory_provider(cfg)
        assert isinstance(provider, FileMemoryProvider)

    # TC-CMP-04 ----------------------------------------------------------------
    @pytest.mark.unit
    def test_redis_backend(self) -> None:
        """MemoryConfig(backend='redis') returns RedisMemoryProvider.

        Redis is not running, so the provider should initialise but set
        _fallback automatically — no actual connection required.
        """
        cfg = MemoryConfig(backend="redis", redis_url="redis://localhost:19999")
        provider = create_memory_provider(cfg)
        assert isinstance(provider, RedisMemoryProvider)

    # TC-CMP-05 ----------------------------------------------------------------
    @pytest.mark.unit
    def test_env_var_override(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When config=None, MEMORY_BACKEND env var drives backend selection."""
        monkeypatch.setenv("MEMORY_BACKEND", "buffer")
        provider = create_memory_provider(None)
        assert isinstance(provider, BufferMemory)

    # TC-CMP-06 ----------------------------------------------------------------
    @pytest.mark.unit
    def test_unknown_backend_falls_to_buffer(self) -> None:
        """An unrecognised backend string falls back to BufferMemory."""
        cfg = MemoryConfig(backend="unknown_xyz")
        provider = create_memory_provider(cfg)
        assert isinstance(provider, BufferMemory)
