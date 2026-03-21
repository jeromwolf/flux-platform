"""Cache abstraction layer.

Provides a pluggable caching system with in-memory and Redis backends.
"""
from kg.cache.backend import CacheBackend
from kg.cache.memory import InMemoryCache
from kg.cache.models import CacheConfig, CacheEntry, CacheStats

__all__ = [
    "CacheBackend",
    "CacheConfig",
    "CacheEntry",
    "CacheStats",
    "InMemoryCache",
]
