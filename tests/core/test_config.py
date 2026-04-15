"""Unit tests for kg.config module."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from kg.config import (
    AppConfig,
    Neo4jConfig,
    close_driver,
    get_config,
    get_driver,
    reset,
    set_config,
    setup_logging,
)


@pytest.fixture(autouse=True)
def _reset_config():
    """Reset config singleton before/after each test."""
    reset()
    yield
    reset()


# =========================================================================
# Neo4jConfig
# =========================================================================


@pytest.mark.unit
class TestNeo4jConfig:
    def test_defaults(self):
        cfg = Neo4jConfig()
        assert cfg.uri == "bolt://localhost:7687"
        assert cfg.user == "neo4j"
        assert cfg.password == ""
        assert cfg.database == "neo4j"
        assert cfg.max_connection_pool_size == 50
        assert cfg.connection_timeout == 30.0

    def test_frozen(self):
        cfg = Neo4jConfig()
        with pytest.raises(AttributeError):
            cfg.uri = "bolt://other:7687"  # type: ignore[misc]

    def test_custom_values(self):
        cfg = Neo4jConfig(uri="bolt://custom:7687", user="admin", password="secret")
        assert cfg.uri == "bolt://custom:7687"
        assert cfg.user == "admin"
        assert cfg.password == "secret"

    def test_equality(self):
        a = Neo4jConfig()
        b = Neo4jConfig()
        assert a == b

    def test_inequality(self):
        a = Neo4jConfig()
        b = Neo4jConfig(uri="bolt://other:7687")
        assert a != b


# =========================================================================
# AppConfig
# =========================================================================


@pytest.mark.unit
class TestAppConfig:
    def test_defaults(self):
        cfg = AppConfig()
        assert cfg.project_name == "maritime-platform"
        assert cfg.env == "production"
        assert cfg.log_level == "INFO"
        assert isinstance(cfg.neo4j, Neo4jConfig)

    def test_default_env_is_production(self):
        cfg = AppConfig()
        from kg.config import Environment
        assert cfg.env == Environment.PRODUCTION

    def test_from_env_with_env_vars(self):
        env_vars = {
            "NEO4J_URI": "bolt://test:7687",
            "NEO4J_USER": "test_user",
            "NEO4J_PASSWORD": "test_pw",
            "NEO4J_DATABASE": "testdb",
            "ENV": "testing",
            "LOG_LEVEL": "DEBUG",
            "PROJECT_NAME": "test-project",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            cfg = AppConfig.from_env()
            assert cfg.neo4j.uri == "bolt://test:7687"
            assert cfg.neo4j.user == "test_user"
            assert cfg.neo4j.password == "test_pw"
            assert cfg.neo4j.database == "testdb"
            assert cfg.env == "testing"
            assert cfg.log_level == "DEBUG"
            assert cfg.project_name == "test-project"

    def test_from_env_uses_defaults_when_no_env(self):
        keys_to_remove = [
            "NEO4J_URI",
            "NEO4J_USER",
            "NEO4J_PASSWORD",
            "NEO4J_DATABASE",
            "ENV",
            "LOG_LEVEL",
            "PROJECT_NAME",
        ]
        clean_env = {k: v for k, v in os.environ.items() if k not in keys_to_remove}
        with patch.dict(os.environ, clean_env, clear=True):
            cfg = AppConfig.from_env()
            assert cfg.neo4j.uri == "bolt://localhost:7687"
            assert cfg.neo4j.user == "neo4j"
            assert cfg.env == "production"

    def test_frozen(self):
        cfg = AppConfig()
        with pytest.raises(AttributeError):
            cfg.env = "production"  # type: ignore[misc]

    def test_from_env_with_explicit_file(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("NEO4J_URI=bolt://from-file:7687\n")
        # Remove NEO4J_URI from env so dotenv can set it (dotenv won't override)
        keys_to_remove = ["NEO4J_URI"]
        clean_env = {k: v for k, v in os.environ.items() if k not in keys_to_remove}
        with patch.dict(os.environ, clean_env, clear=True):
            cfg = AppConfig.from_env(env_file=env_file)
            # dotenv should have loaded the file; the env var takes effect
            assert cfg.neo4j.uri == "bolt://from-file:7687"

    def test_from_env_without_dotenv(self):
        """Graceful degradation when python-dotenv is not installed."""
        # Temporarily make dotenv unimportable
        original_import = (
            __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__
        )

        def mock_import(name, *args, **kwargs):
            if name == "dotenv":
                raise ImportError("No module named 'dotenv'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            # Force re-execution of from_env by calling directly
            cfg = AppConfig.from_env()
            assert isinstance(cfg, AppConfig)


# =========================================================================
# Singleton management
# =========================================================================


@pytest.mark.unit
class TestSingletonManagement:
    def test_get_config_returns_same_instance(self):
        c1 = get_config()
        c2 = get_config()
        assert c1 is c2

    def test_set_config_replaces(self):
        custom = AppConfig(env="custom")
        set_config(custom)
        assert get_config().env == "custom"
        assert get_config() is custom

    def test_set_config_closes_existing_driver(self):
        import kg.config as cfg_module

        mock_driver = MagicMock()
        cfg_module._driver = mock_driver

        set_config(AppConfig(env="new"))
        mock_driver.close.assert_called_once()
        assert cfg_module._driver is None

    def test_set_config_tolerates_driver_close_error(self):
        import kg.config as cfg_module

        mock_driver = MagicMock()
        mock_driver.close.side_effect = RuntimeError("close failed")
        cfg_module._driver = mock_driver

        # Should not raise
        set_config(AppConfig(env="new"))
        assert cfg_module._driver is None

    def test_reset_clears_config(self):
        _ = get_config()
        reset()
        # After reset, a fresh config is created on next access
        # get_config() reads ENV from environment; match the expected value
        cfg = get_config()
        env_expected = os.environ.get("ENV", "production")
        assert cfg.env == env_expected

    def test_get_driver_returns_singleton(self):
        import kg.config as cfg_module

        mock_driver = MagicMock()
        cfg_module._driver = mock_driver
        assert get_driver() is mock_driver

    def test_close_driver_when_none(self):
        # Should not raise
        close_driver()

    def test_close_driver_calls_close(self):
        import kg.config as cfg_module

        mock_driver = MagicMock()
        cfg_module._driver = mock_driver
        close_driver()
        mock_driver.close.assert_called_once()
        assert cfg_module._driver is None

    def test_close_driver_tolerates_error(self):
        import kg.config as cfg_module

        mock_driver = MagicMock()
        mock_driver.close.side_effect = RuntimeError("fail")
        cfg_module._driver = mock_driver
        close_driver()
        assert cfg_module._driver is None


# =========================================================================
# Backward compatibility (__getattr__)
# =========================================================================


@pytest.mark.unit
class TestBackwardCompat:
    def test_legacy_NEO4J_URI_access(self):
        import kg.config as cfg_module

        with pytest.warns(DeprecationWarning, match="deprecated"):
            uri = cfg_module.NEO4J_URI
        assert uri == get_config().neo4j.uri

    def test_legacy_NEO4J_USER_access(self):
        import kg.config as cfg_module

        with pytest.warns(DeprecationWarning, match="deprecated"):
            user = cfg_module.NEO4J_USER
        assert user == "neo4j"

    def test_legacy_NEO4J_PASSWORD_access(self):
        import kg.config as cfg_module

        with pytest.warns(DeprecationWarning, match="deprecated"):
            pw = cfg_module.NEO4J_PASSWORD
        assert pw == get_config().neo4j.password

    def test_legacy_NEO4J_DATABASE_access(self):
        import kg.config as cfg_module

        with pytest.warns(DeprecationWarning, match="deprecated"):
            db = cfg_module.NEO4J_DATABASE
        assert db == "neo4j"

    def test_legacy_PROJECT_NAME_access(self):
        import kg.config as cfg_module

        with pytest.warns(DeprecationWarning, match="deprecated"):
            name = cfg_module.PROJECT_NAME
        assert name == "maritime-platform"

    def test_legacy_ENV_access(self):
        import kg.config as cfg_module

        with pytest.warns(DeprecationWarning, match="deprecated"):
            env = cfg_module.ENV
        env_expected = os.environ.get("ENV", "production")
        assert env == env_expected

    def test_unknown_attr_raises(self):
        import kg.config as cfg_module

        with pytest.raises(AttributeError, match="NONEXISTENT"):
            _ = cfg_module.NONEXISTENT


# =========================================================================
# setup_logging
# =========================================================================


@pytest.mark.unit
class TestSetupLogging:
    def test_setup_logging_with_level(self):
        # Should not raise
        setup_logging("DEBUG")

    def test_setup_logging_uses_config_default(self):
        # Should not raise
        setup_logging()

    def test_setup_logging_with_none(self):
        setup_logging(None)
