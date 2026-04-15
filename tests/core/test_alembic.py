"""Unit tests for Alembic migration framework setup."""
from __future__ import annotations

import importlib.util
import os

import pytest

_ROOT = os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
_ROOT = os.path.normpath(_ROOT)


@pytest.mark.unit
class TestAlembicSetup:
    """Verify that the Alembic directory layout and files are correct."""

    def test_alembic_ini_exists(self) -> None:
        assert os.path.isfile(os.path.join(_ROOT, "alembic.ini"))

    def test_env_py_exists(self) -> None:
        assert os.path.isfile(os.path.join(_ROOT, "alembic", "env.py"))

    def test_script_py_mako_exists(self) -> None:
        assert os.path.isfile(os.path.join(_ROOT, "alembic", "script.py.mako"))

    def test_versions_directory_exists(self) -> None:
        versions_dir = os.path.join(_ROOT, "alembic", "versions")
        assert os.path.isdir(versions_dir)

    def test_initial_migration_exists(self) -> None:
        versions_dir = os.path.join(_ROOT, "alembic", "versions")
        files = os.listdir(versions_dir)
        assert any("001" in f for f in files), f"No 001 migration in {files}"

    def test_env_py_importable(self) -> None:
        """Verify env.py can be parsed as a valid Python module."""
        env_path = os.path.join(_ROOT, "alembic", "env.py")
        spec = importlib.util.spec_from_file_location("alembic_env", env_path)
        assert spec is not None
        assert spec.loader is not None

    def test_migration_has_upgrade_downgrade(self) -> None:
        versions_dir = os.path.join(_ROOT, "alembic", "versions")
        migration_files = [
            f for f in os.listdir(versions_dir) if f.endswith(".py") and "001" in f
        ]
        assert migration_files, "No initial migration file found"

        fpath = os.path.join(versions_dir, migration_files[0])
        spec = importlib.util.spec_from_file_location("migration_001", fpath)
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]

        assert hasattr(mod, "upgrade"), "Migration must define upgrade()"
        assert hasattr(mod, "downgrade"), "Migration must define downgrade()"
        assert callable(mod.upgrade)
        assert callable(mod.downgrade)
        assert mod.revision == "001"
        assert mod.down_revision is None

    def test_alembic_ini_script_location(self) -> None:
        """alembic.ini must point script_location to 'alembic'."""
        ini_path = os.path.join(_ROOT, "alembic.ini")
        with open(ini_path) as f:
            content = f.read()
        assert "script_location = alembic" in content

    def test_env_py_get_url_function(self) -> None:
        """env.py must define a get_url() helper reading env vars."""
        env_path = os.path.join(_ROOT, "alembic", "env.py")
        with open(env_path) as f:
            source = f.read()
        assert "def get_url(" in source
        assert "POSTGRES_USER" in source
        assert "POSTGRES_HOST" in source
        assert "POSTGRES_PORT" in source
        assert "POSTGRES_DB" in source
