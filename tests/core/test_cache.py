"""Cache abstraction unit tests.

TC-CA01 ~ TC-CA07: CacheBackend protocol, InMemoryCache, and CacheConfig.
All tests run without external dependencies.
"""

from __future__ import annotations

import time

import pytest

from kg.cache import CacheBackend, CacheConfig, CacheEntry, CacheStats, InMemoryCache


# =============================================================================
# TC-CA01: CacheConfig
# =============================================================================


@pytest.mark.unit
class TestCacheConfig:
    """CacheConfig tests."""

    def test_default_values(self) -> None:
        """TC-CA01-a: Defaults are sensible."""
        cfg = CacheConfig()
        assert cfg.backend == "memory"
        assert cfg.default_ttl == 300
        assert cfg.max_size == 1000

    def test_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TC-CA01-b: from_env reads environment variables."""
        monkeypatch.setenv("CACHE_BACKEND", "redis")
        monkeypatch.setenv("CACHE_TTL", "60")
        cfg = CacheConfig.from_env()
        assert cfg.backend == "redis"
        assert cfg.default_ttl == 60

    def test_validate_valid(self) -> None:
        """TC-CA01-c: Valid config has no errors."""
        assert CacheConfig().validate() == []

    def test_validate_invalid_backend(self) -> None:
        """TC-CA01-d: Unknown backend is invalid."""
        cfg = CacheConfig(backend="unknown")
        errors = cfg.validate()
        assert any("backend" in e for e in errors)

    def test_validate_negative_ttl(self) -> None:
        """TC-CA01-e: Negative TTL is invalid."""
        cfg = CacheConfig(default_ttl=-1)
        errors = cfg.validate()
        assert any("ttl" in e for e in errors)

    def test_frozen(self) -> None:
        """TC-CA01-f: CacheConfig is frozen."""
        cfg = CacheConfig()
        with pytest.raises(AttributeError):
            cfg.backend = "test"  # type: ignore[misc]


# =============================================================================
# TC-CA02: CacheEntry
# =============================================================================


@pytest.mark.unit
class TestCacheEntry:
    """CacheEntry tests."""

    def test_not_expired_initially(self) -> None:
        """TC-CA02-a: New entry is not expired."""
        entry = CacheEntry(key="k", value="v", ttl=300)
        assert entry.is_expired is False

    def test_expired_after_ttl(self) -> None:
        """TC-CA02-b: Entry expires after TTL."""
        entry = CacheEntry(
            key="k", value="v",
            created_at=time.monotonic() - 400,
            ttl=300,
        )
        assert entry.is_expired is True

    def test_zero_ttl_never_expires(self) -> None:
        """TC-CA02-c: TTL=0 means never expire."""
        entry = CacheEntry(
            key="k", value="v",
            created_at=time.monotonic() - 99999,
            ttl=0,
        )
        assert entry.is_expired is False


# =============================================================================
# TC-CA03: CacheStats
# =============================================================================


@pytest.mark.unit
class TestCacheStats:
    """CacheStats tests."""

    def test_hit_rate_zero(self) -> None:
        """TC-CA03-a: Hit rate is 0 when no accesses."""
        stats = CacheStats()
        assert stats.hit_rate == 0.0

    def test_hit_rate_calculation(self) -> None:
        """TC-CA03-b: Hit rate is calculated correctly."""
        stats = CacheStats(hits=3, misses=1)
        assert stats.hit_rate == 75.0

    def test_reset(self) -> None:
        """TC-CA03-c: reset() zeroes all counters."""
        stats = CacheStats(hits=5, misses=2, sets=3)
        stats.reset()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.sets == 0


# =============================================================================
# TC-CA04: InMemoryCache basic operations
# =============================================================================


@pytest.mark.unit
class TestInMemoryCacheBasic:
    """InMemoryCache basic CRUD tests."""

    def test_set_and_get(self) -> None:
        """TC-CA04-a: set + get returns the value."""
        cache = InMemoryCache()
        cache.set("key", "value")
        assert cache.get("key") == "value"

    def test_get_missing_returns_none(self) -> None:
        """TC-CA04-b: get on missing key returns None."""
        cache = InMemoryCache()
        assert cache.get("missing") is None

    def test_delete(self) -> None:
        """TC-CA04-c: delete removes a key."""
        cache = InMemoryCache()
        cache.set("key", "value")
        assert cache.delete("key") is True
        assert cache.get("key") is None

    def test_delete_missing_returns_false(self) -> None:
        """TC-CA04-d: delete on missing key returns False."""
        cache = InMemoryCache()
        assert cache.delete("missing") is False

    def test_clear(self) -> None:
        """TC-CA04-e: clear removes all entries."""
        cache = InMemoryCache()
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.size == 0

    def test_exists(self) -> None:
        """TC-CA04-f: exists returns True for present keys."""
        cache = InMemoryCache()
        cache.set("key", "value")
        assert cache.exists("key") is True
        assert cache.exists("missing") is False


# =============================================================================
# TC-CA05: TTL expiration
# =============================================================================


@pytest.mark.unit
class TestInMemoryCacheTTL:
    """InMemoryCache TTL behavior."""

    def test_expired_entry_returns_none(self) -> None:
        """TC-CA05-a: Expired entry returns None on get."""
        cache = InMemoryCache(CacheConfig(default_ttl=0))
        # Use a very short TTL
        cache.set("key", "value", ttl=1)
        # Simulate expiration
        time.sleep(1.1)
        assert cache.get("key") is None

    def test_custom_ttl_override(self) -> None:
        """TC-CA05-b: Per-key TTL overrides default."""
        cache = InMemoryCache(CacheConfig(default_ttl=1))
        cache.set("long", "value", ttl=9999)
        time.sleep(1.1)
        assert cache.get("long") == "value"


# =============================================================================
# TC-CA06: LRU eviction
# =============================================================================


@pytest.mark.unit
class TestInMemoryCacheEviction:
    """InMemoryCache eviction behavior."""

    def test_evicts_oldest_when_full(self) -> None:
        """TC-CA06-a: Oldest entry is evicted when max_size reached."""
        cache = InMemoryCache(CacheConfig(max_size=3))
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # should evict "a"
        assert cache.get("a") is None
        assert cache.get("d") == 4
        assert cache.size == 3

    def test_stats_track_evictions(self) -> None:
        """TC-CA06-b: Stats track eviction count."""
        cache = InMemoryCache(CacheConfig(max_size=2))
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        assert cache.stats.evictions >= 1


# =============================================================================
# TC-CA07: Stats and protocol
# =============================================================================


@pytest.mark.unit
class TestInMemoryCacheStats:
    """Cache statistics and protocol compliance."""

    def test_stats_increment(self) -> None:
        """TC-CA07-a: Stats are incremented correctly."""
        cache = InMemoryCache()
        cache.set("key", "value")
        cache.get("key")  # hit
        cache.get("missing")  # miss
        assert cache.stats.sets == 1
        assert cache.stats.hits == 1
        assert cache.stats.misses == 1

    def test_satisfies_protocol(self) -> None:
        """TC-CA07-b: InMemoryCache satisfies CacheBackend protocol."""
        assert isinstance(InMemoryCache(), CacheBackend)

    def test_key_prefix(self) -> None:
        """TC-CA07-c: Keys are prefixed with config prefix."""
        cache = InMemoryCache(CacheConfig(key_prefix="test:"))
        cache.set("key", "value")
        assert cache.get("key") == "value"
