"""Migration data models."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MigrationFile:
    """Parsed migration file metadata."""

    version: str  # e.g. "V001"
    sequence: int  # e.g. 1 (numeric, for sorting)
    description: str  # e.g. "initial_constraints"
    path: Path
    checksum: str  # "sha256:abc123..."
    statements: tuple[str, ...] = ()  # parsed Cypher statements (tuple for frozen)

    @staticmethod
    def compute_checksum(filepath: Path) -> str:
        """Compute SHA-256 checksum of a migration file."""
        content = filepath.read_text(encoding="utf-8")
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return f"sha256:{digest}"


@dataclass(frozen=True)
class AppliedMigration:
    """Record of an already-applied migration from Neo4j."""

    version: str
    description: str
    checksum: str
    applied_at: str  # ISO 8601
    execution_time_ms: int
    environment: str = ""
