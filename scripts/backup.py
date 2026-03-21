"""Neo4j and data backup utility.

Provides backup operations for Neo4j database and data files.
Supports dry-run mode, compression, and rotation.

Usage::

    # Dry run (show what would be backed up)
    python -m scripts.backup --dry-run

    # Full backup to default directory
    python -m scripts.backup

    # Custom output directory
    python -m scripts.backup --output /backups/daily

    # With rotation (keep last N backups)
    python -m scripts.backup --rotate 7

    # Validate a backup
    python -m scripts.backup --validate /backups/daily/backup_20260101_120000.json
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BackupConfig:
    """Backup configuration."""
    output_dir: str = "backups"
    compress: bool = True
    rotate_count: int = 0        # 0 = keep all
    include_data: bool = True    # backup data files
    dry_run: bool = False


@dataclass(frozen=True)
class BackupManifest:
    """Manifest describing a completed backup."""
    timestamp: str
    backup_dir: str
    files: list[str] = field(default_factory=list)
    neo4j_cypher_export: bool = False
    total_size_bytes: int = 0
    duration_seconds: float = 0.0
    status: str = "completed"


class BackupManager:
    """Manages backup operations for the IMSP platform.

    Supports:
    - Cypher-based Neo4j data export (generates APOC export commands)
    - Configuration file backup
    - Schema file backup
    - Backup rotation (delete old backups)
    - Dry-run mode
    """

    def __init__(self, config: BackupConfig | None = None) -> None:
        self._config = config or BackupConfig()

    def create_backup(self) -> BackupManifest:
        """Create a full backup.

        Returns:
            BackupManifest describing the completed backup.
        """
        start_time = time.monotonic()
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        backup_dir = os.path.join(self._config.output_dir, f"backup_{timestamp}")

        if self._config.dry_run:
            logger.info("[DRY RUN] Would create backup at: %s", backup_dir)
            return self._dry_run_manifest(timestamp, backup_dir)

        os.makedirs(backup_dir, exist_ok=True)
        files: list[str] = []

        # 1. Export schema files
        schema_files = self._backup_schema_files(backup_dir)
        files.extend(schema_files)

        # 2. Export config snapshot
        config_file = self._backup_config(backup_dir)
        if config_file:
            files.append(config_file)

        # 3. Generate Neo4j export commands
        cypher_file = self._generate_neo4j_export(backup_dir)
        if cypher_file:
            files.append(cypher_file)

        # 4. Write manifest
        duration = time.monotonic() - start_time
        total_size = sum(
            os.path.getsize(os.path.join(backup_dir, f))
            for f in files
            if os.path.exists(os.path.join(backup_dir, f))
        )

        manifest = BackupManifest(
            timestamp=timestamp,
            backup_dir=backup_dir,
            files=files,
            neo4j_cypher_export=bool(cypher_file),
            total_size_bytes=total_size,
            duration_seconds=round(duration, 2),
        )

        manifest_path = os.path.join(backup_dir, "manifest.json")
        with open(manifest_path, "w") as f:
            json.dump(asdict(manifest), f, indent=2, ensure_ascii=False)
        files.append("manifest.json")

        logger.info(
            "Backup completed: %s (%d files, %d bytes, %.1fs)",
            backup_dir,
            len(files),
            total_size,
            duration,
        )

        # 5. Rotate old backups
        if self._config.rotate_count > 0:
            self._rotate_backups()

        return manifest

    def validate_backup(self, backup_dir: str) -> list[str]:
        """Validate a backup directory.

        Args:
            backup_dir: Path to the backup directory.

        Returns:
            List of validation error messages. Empty = valid.
        """
        errors: list[str] = []

        if not os.path.isdir(backup_dir):
            return [f"Backup directory not found: {backup_dir}"]

        manifest_path = os.path.join(backup_dir, "manifest.json")
        if not os.path.exists(manifest_path):
            errors.append("manifest.json not found")
            return errors

        try:
            with open(manifest_path) as f:
                manifest = json.load(f)
        except json.JSONDecodeError as e:
            errors.append(f"Invalid manifest.json: {e}")
            return errors

        # Check listed files exist
        for file_name in manifest.get("files", []):
            file_path = os.path.join(backup_dir, file_name)
            if not os.path.exists(file_path):
                errors.append(f"Listed file missing: {file_name}")

        if not errors:
            logger.info("Backup validation passed: %s", backup_dir)
        else:
            logger.warning("Backup validation failed: %d issue(s)", len(errors))

        return errors

    def list_backups(self) -> list[dict[str, Any]]:
        """List all backups in the output directory.

        Returns:
            List of backup info dicts with timestamp and path.
        """
        output_dir = self._config.output_dir
        if not os.path.isdir(output_dir):
            return []

        backups = []
        for entry in sorted(os.listdir(output_dir)):
            entry_path = os.path.join(output_dir, entry)
            if os.path.isdir(entry_path) and entry.startswith("backup_"):
                manifest_path = os.path.join(entry_path, "manifest.json")
                info: dict[str, Any] = {"path": entry_path, "name": entry}
                if os.path.exists(manifest_path):
                    try:
                        with open(manifest_path) as f:
                            info["manifest"] = json.load(f)
                    except json.JSONDecodeError:
                        info["manifest"] = None
                backups.append(info)

        return backups

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _backup_schema_files(self, backup_dir: str) -> list[str]:
        """Copy schema .cypher files to backup directory."""
        schema_dir = os.path.join("domains", "maritime", "schema")
        files: list[str] = []
        if not os.path.isdir(schema_dir):
            logger.debug("Schema directory not found: %s", schema_dir)
            return files

        schema_backup_dir = os.path.join(backup_dir, "schema")
        os.makedirs(schema_backup_dir, exist_ok=True)

        for fname in os.listdir(schema_dir):
            if fname.endswith(".cypher"):
                src = os.path.join(schema_dir, fname)
                dst = os.path.join(schema_backup_dir, fname)
                shutil.copy2(src, dst)
                files.append(os.path.join("schema", fname))
                logger.debug("Backed up schema: %s", fname)

        return files

    def _backup_config(self, backup_dir: str) -> str | None:
        """Export current configuration snapshot."""
        try:
            from kg.config import get_config

            config = get_config()
            config_data = {
                "project_name": config.project_name,
                "env": config.env,
                "log_level": config.log_level,
                "neo4j_uri": config.neo4j.uri,
                "neo4j_database": config.neo4j.database,
                # Explicitly exclude password
            }
            config_path = os.path.join(backup_dir, "config_snapshot.json")
            with open(config_path, "w") as f:
                json.dump(config_data, f, indent=2)
            return "config_snapshot.json"
        except Exception as exc:
            logger.warning("Failed to export config: %s", exc)
            return None

    def _generate_neo4j_export(self, backup_dir: str) -> str | None:
        """Generate Neo4j APOC export Cypher commands."""
        export_commands = [
            "// Neo4j APOC Export Commands",
            "// Run these in Neo4j Browser or cypher-shell to export data",
            "//",
            "// Export all nodes and relationships as JSON:",
            "CALL apoc.export.json.all('export_full.json', {useTypes: true});",
            "",
            "// Export as Cypher statements:",
            "CALL apoc.export.cypher.all('export_full.cypher', {format: 'neo4j-shell'});",
            "",
            "// Export as CSV:",
            "CALL apoc.export.csv.all('export_full.csv', {});",
        ]

        export_path = os.path.join(backup_dir, "neo4j_export_commands.cypher")
        with open(export_path, "w") as f:
            f.write("\n".join(export_commands))
        return "neo4j_export_commands.cypher"

    def _dry_run_manifest(self, timestamp: str, backup_dir: str) -> BackupManifest:
        """Generate a manifest for dry-run mode."""
        return BackupManifest(
            timestamp=timestamp,
            backup_dir=backup_dir,
            files=["[dry run — no files created]"],
            status="dry_run",
        )

    def _rotate_backups(self) -> None:
        """Delete old backups exceeding rotate_count."""
        output_dir = self._config.output_dir
        if not os.path.isdir(output_dir):
            return

        backup_dirs = sorted(
            [
                d
                for d in os.listdir(output_dir)
                if os.path.isdir(os.path.join(output_dir, d))
                and d.startswith("backup_")
            ]
        )

        while len(backup_dirs) > self._config.rotate_count:
            oldest = backup_dirs.pop(0)
            oldest_path = os.path.join(output_dir, oldest)
            logger.info("Rotating old backup: %s", oldest_path)
            shutil.rmtree(oldest_path)


def main() -> None:
    """CLI entry point for backup operations."""
    parser = argparse.ArgumentParser(
        description="IMSP Platform Backup Utility",
    )
    parser.add_argument(
        "--output", "-o",
        default="backups",
        help="Output directory for backups (default: backups/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be backed up without creating files",
    )
    parser.add_argument(
        "--rotate",
        type=int,
        default=0,
        help="Keep only the last N backups (0 = keep all)",
    )
    parser.add_argument(
        "--validate",
        type=str,
        default=None,
        help="Validate an existing backup directory",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all existing backups",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    config = BackupConfig(
        output_dir=args.output,
        dry_run=args.dry_run,
        rotate_count=args.rotate,
    )
    manager = BackupManager(config)

    if args.validate:
        errors = manager.validate_backup(args.validate)
        if errors:
            for err in errors:
                print(f"  ERROR: {err}")
            sys.exit(1)
        else:
            print("Backup is valid.")
            sys.exit(0)

    if args.list:
        backups = manager.list_backups()
        if not backups:
            print("No backups found.")
        else:
            for b in backups:
                m = b.get("manifest", {})
                ts = m.get("timestamp", "unknown") if m else "unknown"
                size = m.get("total_size_bytes", 0) if m else 0
                print(f"  {b['name']}  (timestamp={ts}, size={size} bytes)")
        sys.exit(0)

    manifest = manager.create_backup()
    print(f"Backup {'simulated' if args.dry_run else 'completed'}: {manifest.backup_dir}")
    print(f"  Files: {len(manifest.files)}")
    print(f"  Size: {manifest.total_size_bytes} bytes")
    print(f"  Duration: {manifest.duration_seconds}s")


if __name__ == "__main__":
    main()
