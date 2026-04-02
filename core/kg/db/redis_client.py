"""Redis client management for IMSP services.

Uses DB 1 for rate limiting (DB 0 reserved for application services).
"""
from __future__ import annotations

import contextlib
import logging
from typing import Any

logger = logging.getLogger(__name__)

_redis_client: Any = None


def get_redis_client() -> Any | None:
    """Get or create the Redis client singleton.

    Returns None if redis package is not installed or connection fails.
    """
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    try:
        import redis
        from kg.config import get_config

        cfg = get_config().redis
        client = redis.from_url(cfg.url, decode_responses=True)
        client.ping()
        _redis_client = client
        logger.info("Redis client connected: %s", cfg.url)
        return _redis_client
    except Exception as exc:
        logger.warning(
            "Redis unavailable (%s) -- rate limiting will use in-memory fallback", exc
        )
        return None


def close_redis_client() -> None:
    """Close the Redis client."""
    global _redis_client
    if _redis_client is not None:
        with contextlib.suppress(Exception):
            _redis_client.close()
        _redis_client = None
        logger.info("Redis client closed")


def reset_redis_client() -> None:
    """Reset client reference without closing (for testing)."""
    global _redis_client
    _redis_client = None
