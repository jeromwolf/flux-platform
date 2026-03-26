"""Raw data storage layer for ELT pipeline.

Provides a Protocol for raw data persistence (Extract → Load Raw)
with implementations for local filesystem (Y1) and future object
storage backends (MinIO/Ceph for Y2+).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class RawStore(Protocol):
    """Protocol for raw data storage backends."""

    def put(self, key: str, data: bytes, metadata: dict[str, Any] | None = None) -> str:
        """Store raw data. Returns the storage key."""
        ...

    def get(self, key: str) -> bytes | None:
        """Retrieve raw data by key. Returns None if not found."""
        ...

    def exists(self, key: str) -> bool:
        """Check if a key exists in the store."""
        ...

    def list_keys(self, prefix: str = "") -> list[str]:
        """List keys matching a prefix."""
        ...

    def delete(self, key: str) -> bool:
        """Delete a key. Returns True if it existed."""
        ...

    def get_metadata(self, key: str) -> dict[str, Any] | None:
        """Get metadata for a stored object. Returns None if not found."""
        ...


class NullRawStore:
    """No-op raw store for backward-compatible ETL mode.

    When no raw storage is configured, records flow directly
    through the pipeline without raw persistence (classic ETL).
    """

    def put(self, key: str, data: bytes, metadata: dict[str, Any] | None = None) -> str:
        return key

    def get(self, key: str) -> bytes | None:
        return None

    def exists(self, key: str) -> bool:
        return False

    def list_keys(self, prefix: str = "") -> list[str]:
        return []

    def delete(self, key: str) -> bool:
        return False

    def get_metadata(self, key: str) -> dict[str, Any] | None:
        return None


class LocalFileStore:
    """Local filesystem raw store for development/Y1.

    Stores raw data under a base directory with the structure:
        {base_dir}/{source}/{YYYY-MM-DD}/{record_id}.json
        {base_dir}/{source}/{YYYY-MM-DD}/{record_id}.meta.json

    Args:
        base_dir: Root directory for raw data storage.
                  Defaults to .imsp/raw/
    """

    def __init__(self, base_dir: str = ".imsp/raw") -> None:
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)

    def put(self, key: str, data: bytes, metadata: dict[str, Any] | None = None) -> str:
        """Store raw data to local filesystem."""
        path = self._base / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

        if metadata:
            meta_path = path.with_suffix(path.suffix + ".meta.json")
            meta_path.write_text(
                json.dumps(metadata, ensure_ascii=False, default=str),
                encoding="utf-8",
            )

        logger.debug("Raw data stored: %s (%d bytes)", key, len(data))
        return key

    def get(self, key: str) -> bytes | None:
        """Retrieve raw data from local filesystem."""
        path = self._base / key
        if not path.exists():
            return None
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        return (self._base / key).exists()

    def list_keys(self, prefix: str = "") -> list[str]:
        """List all keys under a prefix directory."""
        search_path = self._base / prefix
        if not search_path.exists():
            return []
        keys = []
        for p in search_path.rglob("*"):
            if p.is_file() and not p.name.endswith(".meta.json"):
                keys.append(str(p.relative_to(self._base)))
        return sorted(keys)

    def delete(self, key: str) -> bool:
        path = self._base / key
        if not path.exists():
            return False
        path.unlink()
        # Also delete metadata file
        meta_path = path.with_suffix(path.suffix + ".meta.json")
        if meta_path.exists():
            meta_path.unlink()
        return True

    def get_metadata(self, key: str) -> dict[str, Any] | None:
        path = self._base / key
        meta_path = path.with_suffix(path.suffix + ".meta.json")
        if not meta_path.exists():
            return None
        return json.loads(meta_path.read_text(encoding="utf-8"))


def make_raw_key(source: str, record_id: str, ext: str = ".json") -> str:
    """Generate a raw storage key with date partitioning.

    Format: {source}/{YYYY-MM-DD}/{record_id}{ext}
    """
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"{source}/{date_str}/{record_id}{ext}"
