"""Data models for the cache layer."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CacheConfig:
    """Cache configuration.

    Load from environment variables via ``from_env()``.
    """
    backend: str = "memory"          # "memory" or "redis"
    default_ttl: int = 300           # seconds (5 minutes)
    max_size: int = 1000             # max entries for in-memory cache
    redis_url: str = "redis://localhost:6379/0"
    key_prefix: str = "imsp:"

    @classmethod
    def from_env(cls) -> CacheConfig:
        """Load cache configuration from environment variables."""
        return cls(
            backend=os.getenv("CACHE_BACKEND", cls.backend),
            default_ttl=int(os.getenv("CACHE_TTL", str(cls.default_ttl))),
            max_size=int(os.getenv("CACHE_MAX_SIZE", str(cls.max_size))),
            redis_url=os.getenv("REDIS_URL", cls.redis_url),
            key_prefix=os.getenv("CACHE_KEY_PREFIX", cls.key_prefix),
        )

    def validate(self) -> list[str]:
        """Validate configuration. Returns list of error messages."""
        errors: list[str] = []
        if self.backend not in ("memory", "redis"):
            errors.append(f"Unknown cache backend: {self.backend}")
        if self.default_ttl < 0:
            errors.append("default_ttl must be non-negative")
        if self.max_size <= 0:
            errors.append("max_size must be positive")
        return errors


@dataclass(frozen=True)
class CacheEntry:
    """An individual cache entry with metadata."""
    key: str
    value: object
    created_at: float = field(default_factory=time.monotonic)
    ttl: int = 300  # seconds
    hit_count: int = 0

    @property
    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        if self.ttl <= 0:
            return False  # TTL 0 = never expire
        return (time.monotonic() - self.created_at) > self.ttl


@dataclass
class CacheStats:
    """Mutable cache statistics."""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    evictions: int = 0
    expirations: int = 0

    @property
    def hit_rate(self) -> float:
        """Cache hit rate as a percentage (0-100)."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return (self.hits / total) * 100

    def reset(self) -> None:
        """Reset all counters to zero."""
        self.hits = 0
        self.misses = 0
        self.sets = 0
        self.evictions = 0
        self.expirations = 0
