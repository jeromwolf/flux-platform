"""FastAPI dependency injection functions.

Provides ``Depends``-compatible callables for Neo4j driver, session,
and application configuration.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from typing import Any

from kg.config import AppConfig, get_config, get_driver


def get_neo4j_driver() -> Any:
    """Return the shared Neo4j driver singleton.

    Returns:
        The Neo4j driver instance.
    """
    return get_driver()


def get_neo4j_session() -> Generator[Any, None, None]:
    """Yield a Neo4j session scoped to a single request.

    The session is automatically closed when the request finishes.

    Yields:
        A Neo4j session bound to the configured database.
    """
    driver = get_driver()
    cfg = get_config()
    session = driver.session(database=cfg.neo4j.database)
    try:
        yield session
    finally:
        session.close()


async def get_async_neo4j_session() -> AsyncGenerator[Any, None]:
    """Yield an async Neo4j session scoped to a single request.

    The session is automatically closed when the request finishes.

    Yields:
        An async Neo4j session bound to the configured database.
    """
    from kg.config import get_async_driver

    driver = get_async_driver()
    cfg = get_config()
    session = driver.session(database=cfg.neo4j.database)
    try:
        yield session
    finally:
        await session.close()


def get_app_config() -> AppConfig:
    """Return the current application configuration.

    Returns:
        The active :class:`~kg.config.AppConfig` singleton.
    """
    return get_config()
