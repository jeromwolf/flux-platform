"""Neo4j migration runner.

Discovers versioned .cypher files, tracks applied migrations via
:Migration nodes in Neo4j, and applies pending migrations.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from migrations.models import AppliedMigration, MigrationFile

logger = logging.getLogger(__name__)

# Pattern: V001__description.cypher
_MIGRATION_PATTERN = re.compile(r"^V(\d{3})__(.+)\.cypher$")


class MigrationRunner:
    """Discovers and applies Neo4j schema migrations.

    Migrations are versioned .cypher files following the naming convention
    ``V{NNN}__{description}.cypher``. Applied migrations are tracked as
    ``:Migration`` nodes in Neo4j.

    Args:
        driver: Neo4j driver instance.
        database: Neo4j database name.
    """

    def __init__(self, driver: Any, database: str = "neo4j") -> None:
        self._driver = driver
        self._database = database

    def _ensure_migration_constraint(self) -> None:
        """Create the :Migration version unique constraint if not exists."""
        with self._driver.session(database=self._database) as session:
            session.run(
                "CREATE CONSTRAINT migration_version_unique IF NOT EXISTS "
                "FOR (m:Migration) REQUIRE m.version IS UNIQUE"
            )

    def get_applied_versions(self) -> dict[str, AppliedMigration]:
        """Query Neo4j for all applied migrations.

        Returns:
            Dict mapping version string to AppliedMigration.
        """
        with self._driver.session(database=self._database) as session:
            result = session.run(
                "MATCH (m:Migration) "
                "RETURN m.version AS version, m.description AS description, "
                "m.checksum AS checksum, m.appliedAt AS appliedAt, "
                "m.executionTimeMs AS executionTimeMs, "
                "m.environment AS environment "
                "ORDER BY m.version"
            )
            applied: dict[str, AppliedMigration] = {}
            for record in result:
                ver = record["version"]
                applied[ver] = AppliedMigration(
                    version=ver,
                    description=record["description"],
                    checksum=record["checksum"],
                    applied_at=record["appliedAt"],
                    execution_time_ms=record["executionTimeMs"],
                    environment=record.get("environment", ""),
                )
            return applied

    def discover_migrations(self, migrations_dir: Path) -> list[MigrationFile]:
        """Scan a directory for migration files.

        Args:
            migrations_dir: Directory containing V{NNN}__*.cypher files.

        Returns:
            List of MigrationFile sorted by sequence number.
        """
        # Import here to allow standalone usage without full kg package
        try:
            from kg.utils.cypher_parser import parse_cypher_file
        except ImportError:
            from migrations._cypher_parser_fallback import parse_cypher_file  # type: ignore[no-redef]

        migrations: list[MigrationFile] = []
        for filepath in sorted(migrations_dir.glob("V*.cypher")):
            match = _MIGRATION_PATTERN.match(filepath.name)
            if not match:
                logger.warning("Skipping non-matching file: %s", filepath.name)
                continue
            seq = int(match.group(1))
            desc = match.group(2)
            checksum = MigrationFile.compute_checksum(filepath)
            stmts = tuple(parse_cypher_file(filepath))
            migrations.append(
                MigrationFile(
                    version=f"V{seq:03d}",
                    sequence=seq,
                    description=desc,
                    path=filepath,
                    checksum=checksum,
                    statements=stmts,
                )
            )
        return sorted(migrations, key=lambda m: m.sequence)

    def apply(
        self,
        migration: MigrationFile,
        *,
        dry_run: bool = False,
        environment: str = "",
    ) -> None:
        """Apply a single migration.

        Args:
            migration: The migration to apply.
            dry_run: If True, log statements without executing.
            environment: Environment tag (e.g. "production", "staging").
        """
        logger.info(
            "Applying %s: %s (%d statements)%s",
            migration.version,
            migration.description,
            len(migration.statements),
            " [DRY RUN]" if dry_run else "",
        )

        if dry_run:
            for stmt in migration.statements:
                logger.info("  [DRY] %s", stmt[:120])
            return

        start = time.monotonic()
        with self._driver.session(database=self._database) as session:
            with session.begin_transaction() as tx:
                for stmt in migration.statements:
                    logger.debug("  Executing: %s", stmt[:120])
                    tx.run(stmt)
                # Record the migration
                elapsed_ms = int((time.monotonic() - start) * 1000)
                tx.run(
                    "CREATE (m:Migration {"
                    "  version: $version,"
                    "  description: $description,"
                    "  checksum: $checksum,"
                    "  appliedAt: $appliedAt,"
                    "  executionTimeMs: $executionTimeMs,"
                    "  environment: $environment"
                    "})",
                    version=migration.version,
                    description=migration.description,
                    checksum=migration.checksum,
                    appliedAt=datetime.now(timezone.utc).isoformat(),
                    executionTimeMs=elapsed_ms,
                    environment=environment,
                )
                tx.commit()

        logger.info("  Applied %s in %dms", migration.version, elapsed_ms)

    def run_pending(
        self,
        migrations_dir: Path,
        *,
        target: str | None = None,
        dry_run: bool = False,
        environment: str = "",
    ) -> int:
        """Discover and apply all pending migrations.

        Args:
            migrations_dir: Directory with migration files.
            target: Optional target version (e.g. "V003"). Only apply up to this.
            dry_run: If True, print without executing.
            environment: Environment tag.

        Returns:
            Number of migrations applied.
        """
        if not dry_run:
            self._ensure_migration_constraint()

        all_migrations = self.discover_migrations(migrations_dir)
        applied = self.get_applied_versions() if not dry_run else {}

        pending = [m for m in all_migrations if m.version not in applied]

        if target:
            pending = [m for m in pending if m.version <= target]

        if not pending:
            logger.info("No pending migrations.")
            return 0

        # Verify checksums of already-applied migrations
        for m in all_migrations:
            if m.version in applied:
                stored = applied[m.version]
                if stored.checksum != m.checksum:
                    raise ValueError(
                        f"Checksum mismatch for {m.version}: "
                        f"stored={stored.checksum}, file={m.checksum}. "
                        f"Migration files must not be modified after applying."
                    )

        logger.info("Found %d pending migration(s).", len(pending))
        count = 0
        for migration in pending:
            self.apply(migration, dry_run=dry_run, environment=environment)
            count += 1
        return count

    def validate(self, migrations_dir: Path) -> list[str]:
        """Validate migration files without applying.

        Returns:
            List of validation error messages. Empty list means all OK.
        """
        errors: list[str] = []
        migrations = self.discover_migrations(migrations_dir)

        # Check sequence continuity
        for i, m in enumerate(migrations):
            expected_seq = i + 1
            if m.sequence != expected_seq:
                errors.append(
                    f"Gap in sequence: expected V{expected_seq:03d}, "
                    f"found {m.version}"
                )

        # Check for empty migrations
        for m in migrations:
            if not m.statements:
                errors.append(f"{m.version} has no executable statements")

        return errors

    def status(self, migrations_dir: Path) -> list[dict[str, Any]]:
        """Show status of all migrations.

        Returns:
            List of dicts with version, description, status, applied_at.
        """
        all_migrations = self.discover_migrations(migrations_dir)
        applied = self.get_applied_versions()

        result: list[dict[str, Any]] = []
        for m in all_migrations:
            if m.version in applied:
                a = applied[m.version]
                result.append({
                    "version": m.version,
                    "description": m.description,
                    "status": "applied",
                    "applied_at": a.applied_at,
                    "execution_time_ms": a.execution_time_ms,
                })
            else:
                result.append({
                    "version": m.version,
                    "description": m.description,
                    "status": "pending",
                    "applied_at": None,
                    "execution_time_ms": None,
                })
        return result
