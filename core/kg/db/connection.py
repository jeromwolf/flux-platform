"""asyncpg connection pool management.

Provides get_pg_pool() / close_pg_pool() following the same singleton
pattern as kg.config.get_driver() / close_driver().
"""
from __future__ import annotations

import contextlib
import logging
from typing import Any

logger = logging.getLogger(__name__)

_pool: Any = None  # asyncpg.Pool | None


async def get_pg_pool() -> Any:
    """Get or create the asyncpg connection pool singleton.

    Follows the same lazy-singleton pattern as :func:`kg.config.get_driver`.
    Returns ``None`` if asyncpg is not installed or the connection fails,
    allowing callers to fall back to the in-memory repository.

    Returns:
        An ``asyncpg.Pool`` instance, or ``None`` on failure.
    """
    global _pool
    if _pool is not None:
        return _pool

    try:
        import asyncpg
        from kg.config import get_config

        cfg = get_config().postgres
        _pool = await asyncpg.create_pool(
            host=cfg.host,
            port=cfg.port,
            user=cfg.user,
            password=cfg.password,
            database=cfg.database,
            min_size=cfg.min_pool_size,
            max_size=cfg.max_pool_size,
            command_timeout=cfg.command_timeout,
        )
        logger.info(
            "PostgreSQL pool created: %s:%d/%s", cfg.host, cfg.port, cfg.database
        )
        return _pool
    except Exception as exc:
        logger.warning(
            "PostgreSQL unavailable (%s) -- using in-memory fallback", exc
        )
        return None


async def close_pg_pool() -> None:
    """Close the asyncpg pool and release all connections.

    Safe to call multiple times; subsequent calls are no-ops.
    """
    global _pool
    if _pool is not None:
        with contextlib.suppress(Exception):
            await _pool.close()
        _pool = None
        logger.info("PostgreSQL pool closed")


def reset_pg_pool() -> None:
    """Reset the pool reference without closing (for testing).

    Use this in test teardown when the pool has already been closed or was
    never opened, to prevent ``get_pg_pool`` from returning a stale reference.
    """
    global _pool
    _pool = None
