"""Backup utility unit tests.

TC-BK01 ~ TC-BK05: BackupManager behavior tests.
All tests run without external dependencies.
"""

from __future__ import annotations

import json
import os
import tempfile

import pytest

from scripts.backup import BackupConfig, BackupManager, BackupManifest


# =============================================================================
# TC-BK01: BackupConfig
# =============================================================================


@pytest.mark.unit
class TestBackupConfig:
    """BackupConfig tests."""

    def test_default_values(self) -> None:
        """TC-BK01-a: Default config has sensible values."""
        cfg = BackupConfig()
        assert cfg.output_dir == "backups"
        assert cfg.compress is True
        assert cfg.dry_run is False

    def test_frozen(self) -> None:
        """TC-BK01-b: BackupConfig is frozen."""
        cfg = BackupConfig()
        with pytest.raises(AttributeError):
            cfg.output_dir = "test"  # type: ignore[misc]


# =============================================================================
# TC-BK02: Dry run
# =============================================================================


@pytest.mark.unit
class TestBackupDryRun:
    """Dry run mode tests."""

    def test_dry_run_creates_no_files(self) -> None:
        """TC-BK02-a: Dry run does not create any files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = BackupConfig(output_dir=tmpdir, dry_run=True)
            manager = BackupManager(config)
            manifest = manager.create_backup()
            assert manifest.status == "dry_run"
            # No backup subdirectory should be created
            entries = [e for e in os.listdir(tmpdir) if e.startswith("backup_")]
            assert len(entries) == 0

    def test_dry_run_returns_manifest(self) -> None:
        """TC-BK02-b: Dry run returns a valid manifest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = BackupConfig(output_dir=tmpdir, dry_run=True)
            manifest = BackupManager(config).create_backup()
            assert isinstance(manifest, BackupManifest)
            assert manifest.timestamp != ""


# =============================================================================
# TC-BK03: Real backup
# =============================================================================


@pytest.mark.unit
class TestBackupCreation:
    """Actual backup creation tests."""

    def test_creates_backup_directory(self) -> None:
        """TC-BK03-a: Backup creates a timestamped directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = BackupConfig(output_dir=tmpdir, dry_run=False)
            manifest = BackupManager(config).create_backup()
            assert os.path.isdir(manifest.backup_dir)
            assert manifest.status == "completed"

    def test_creates_manifest_file(self) -> None:
        """TC-BK03-b: Backup creates manifest.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = BackupConfig(output_dir=tmpdir)
            manifest = BackupManager(config).create_backup()
            manifest_path = os.path.join(manifest.backup_dir, "manifest.json")
            assert os.path.exists(manifest_path)
            with open(manifest_path) as f:
                data = json.load(f)
            assert data["status"] == "completed"

    def test_creates_neo4j_export_commands(self) -> None:
        """TC-BK03-c: Backup creates neo4j export commands file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = BackupConfig(output_dir=tmpdir)
            manifest = BackupManager(config).create_backup()
            export_file = os.path.join(
                manifest.backup_dir, "neo4j_export_commands.cypher"
            )
            assert os.path.exists(export_file)


# =============================================================================
# TC-BK04: Validation
# =============================================================================


@pytest.mark.unit
class TestBackupValidation:
    """Backup validation tests."""

    def test_validate_valid_backup(self) -> None:
        """TC-BK04-a: Valid backup passes validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = BackupConfig(output_dir=tmpdir)
            manager = BackupManager(config)
            manifest = manager.create_backup()
            errors = manager.validate_backup(manifest.backup_dir)
            assert len(errors) == 0

    def test_validate_missing_directory(self) -> None:
        """TC-BK04-b: Missing directory fails validation."""
        manager = BackupManager()
        errors = manager.validate_backup("/nonexistent/path")
        assert len(errors) > 0

    def test_validate_missing_manifest(self) -> None:
        """TC-BK04-c: Directory without manifest fails validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            errors = BackupManager().validate_backup(tmpdir)
            assert any("manifest" in e.lower() for e in errors)


# =============================================================================
# TC-BK05: Rotation
# =============================================================================


@pytest.mark.unit
class TestBackupRotation:
    """Backup rotation tests."""

    def test_rotation_removes_old_backups(self) -> None:
        """TC-BK05-a: Rotation keeps only the last N backups."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = BackupConfig(output_dir=tmpdir, rotate_count=2)
            manager = BackupManager(config)
            # Create 3 backups
            manager.create_backup()
            manager.create_backup()
            manager.create_backup()
            # Should only keep 2
            backups = manager.list_backups()
            assert len(backups) == 2

    def test_list_backups(self) -> None:
        """TC-BK05-b: list_backups returns correct info."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = BackupConfig(output_dir=tmpdir)
            manager = BackupManager(config)
            manager.create_backup()
            backups = manager.list_backups()
            assert len(backups) == 1
            assert "manifest" in backups[0]

    def test_list_empty_directory(self) -> None:
        """TC-BK05-c: list_backups on empty dir returns empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = BackupManager(BackupConfig(output_dir=tmpdir))
            assert manager.list_backups() == []
