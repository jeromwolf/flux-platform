"""Configuration management for the Maritime KG platform.

Provides:
- Neo4jConfig / PostgresConfig / RedisConfig / AppConfig frozen dataclasses
- get_config() / set_config() for singleton management
- get_driver() / close_driver() for Neo4j connection pool
- Backward-compatible module-level attribute access via __getattr__
"""

from __future__ import annotations

import contextlib
import logging
import os
import warnings
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class Environment(str, Enum):
    """Valid application environment identifiers.

    Using ``str`` mixin so that comparisons like ``config.env == "development"``
    continue to work without changes to existing call sites.
    """

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


@dataclass(frozen=True)
class Neo4jConfig:
    """Immutable Neo4j connection configuration."""

    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = ""  # noqa: S105
    database: str = "neo4j"
    max_connection_pool_size: int = 50
    connection_timeout: float = 30.0


@dataclass(frozen=True)
class PostgresConfig:
    """PostgreSQL connection configuration."""

    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: str = ""  # noqa: S105
    database: str = "imsp"
    min_pool_size: int = 2
    max_pool_size: int = 10
    command_timeout: float = 30.0


@dataclass(frozen=True)
class RedisConfig:
    """Redis connection configuration."""

    url: str = "redis://localhost:6379/1"  # DB 1 (DB 0 reserved for application services)


@dataclass(frozen=True)
class AppConfig:
    """Application-level configuration."""

    project_name: str = "maritime-platform"
    env: Environment = Environment.PRODUCTION
    log_level: str = "INFO"
    neo4j: Neo4jConfig = field(default_factory=Neo4jConfig)
    postgres: PostgresConfig = field(default_factory=PostgresConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> AppConfig:
        """Load configuration from environment variables and optional .env file."""
        try:
            from dotenv import load_dotenv
        except ImportError:
            load_dotenv = None  # type: ignore[assignment]

        if load_dotenv is not None:
            if env_file and env_file.exists():
                load_dotenv(env_file)
            elif env_file is None:
                _root = Path(__file__).resolve().parent.parent
                for candidate in [_root / ".env", _root / ".env.example"]:
                    if candidate.exists():
                        load_dotenv(candidate)
                        break

        neo4j = Neo4jConfig(
            uri=os.getenv("NEO4J_URI", Neo4jConfig.uri),
            user=os.getenv("NEO4J_USER", Neo4jConfig.user),
            password=os.getenv("NEO4J_PASSWORD", Neo4jConfig.password),
            database=os.getenv("NEO4J_DATABASE", Neo4jConfig.database),
        )
        postgres = PostgresConfig(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", ""),  # noqa: S105
            database=os.getenv("POSTGRES_DATABASE", "imsp"),
        )
        redis = RedisConfig(
            url=os.getenv("REDIS_URL", "redis://localhost:6379/1"),
        )
        env_str = os.getenv("ENV", cls.env.value if isinstance(cls.env, Environment) else cls.env)
        try:
            env = Environment(env_str)
        except ValueError:
            valid = ", ".join(e.value for e in Environment)
            raise ValueError(
                f"Invalid ENV value '{env_str}'. Must be one of: {valid}"
            ) from None

        return cls(
            project_name=os.getenv("PROJECT_NAME", cls.project_name),
            env=env,
            log_level=os.getenv("LOG_LEVEL", cls.log_level),
            neo4j=neo4j,
            postgres=postgres,
            redis=redis,
        )


# ---------------------------------------------------------------------------
# Singleton management
# ---------------------------------------------------------------------------

_config: AppConfig | None = None
_driver: Any = None
_async_driver: Any = None


def get_config() -> AppConfig:
    """Get the current application configuration (lazy singleton)."""
    global _config
    if _config is None:
        _config = AppConfig.from_env()
    return _config


def set_config(config: AppConfig) -> None:
    """Override the active configuration. Closes existing driver if any."""
    global _config, _driver
    if _driver is not None:
        with contextlib.suppress(Exception):
            _driver.close()
        _driver = None
    _config = config


def get_driver() -> Any:
    """Get the Neo4j driver singleton. Reuses connection pool.

    Example::

        driver = get_driver()
        cfg = get_config()
        with driver.session(database=cfg.neo4j.database) as session:
            result = session.run("RETURN 1 AS n")
            print(result.single()["n"])
    """
    global _driver
    if _driver is None:
        from neo4j import GraphDatabase

        cfg = get_config().neo4j
        _driver = GraphDatabase.driver(
            cfg.uri,
            auth=(cfg.user, cfg.password),
            max_connection_pool_size=cfg.max_connection_pool_size,
            connection_timeout=cfg.connection_timeout,
        )
    return _driver


def close_driver() -> None:
    """Close the Neo4j driver and release connection pool."""
    global _driver
    if _driver is not None:
        with contextlib.suppress(Exception):
            _driver.close()
        _driver = None


def get_async_driver() -> Any:
    """Get the async Neo4j driver singleton.

    Returns:
        The async Neo4j driver instance.

    Example::

        driver = get_async_driver()
        cfg = get_config()
        async with driver.session(database=cfg.neo4j.database) as session:
            result = await session.run("RETURN 1 AS n")
            record = await result.single()
            print(record["n"])
    """
    global _async_driver
    if _async_driver is None:
        from neo4j import AsyncGraphDatabase

        cfg = get_config().neo4j
        _async_driver = AsyncGraphDatabase.driver(
            cfg.uri,
            auth=(cfg.user, cfg.password),
            max_connection_pool_size=cfg.max_connection_pool_size,
            connection_timeout=cfg.connection_timeout,
        )
    return _async_driver


async def close_async_driver() -> None:
    """Close the async Neo4j driver and release connection pool."""
    global _async_driver
    if _async_driver is not None:
        with contextlib.suppress(Exception):
            await _async_driver.close()
        _async_driver = None


def reset() -> None:
    """Reset both config and driver (for testing)."""
    global _config, _driver, _async_driver
    close_driver()
    # Synchronously clear async driver reference without awaiting close
    _async_driver = None
    _config = None


def setup_logging(level: str | None = None) -> None:
    """Configure logging for the application.

    Args:
        level: Log level string (e.g. "INFO", "DEBUG"). Falls back to
               the ``log_level`` value from :func:`get_config` when *None*.
    """
    cfg = get_config()
    log_level = level or cfg.log_level
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# ---------------------------------------------------------------------------
# Backward-compatible module-level constants (PEP 562)
# ---------------------------------------------------------------------------


def __getattr__(name: str) -> Any:
    """Support legacy access like ``from kg.config import NEO4J_URI``.

    Issues a :class:`DeprecationWarning` so callers can migrate at their
    own pace.
    """
    _COMPAT = {
        "NEO4J_URI": lambda: get_config().neo4j.uri,
        "NEO4J_USER": lambda: get_config().neo4j.user,
        "NEO4J_PASSWORD": lambda: get_config().neo4j.password,
        "NEO4J_DATABASE": lambda: get_config().neo4j.database,
        "PROJECT_NAME": lambda: get_config().project_name,
        "ENV": lambda: get_config().env,
    }
    if name in _COMPAT:
        warnings.warn(
            f"kg.config.{name} is deprecated. Use get_config() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return _COMPAT[name]()
    raise AttributeError(f"module 'kg.config' has no attribute {name!r}")
