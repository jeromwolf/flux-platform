"""File-backed Dead Letter Queue for streaming ingestion failures.

Provides:
- PersistentDLQManager: DLQ that mirrors every entry to a JSON Lines file,
  enabling recovery across process restarts.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from kg.etl.dlq import DLQEntry
from kg.etl.models import RecordEnvelope


class PersistentDLQManager:
    """Dead Letter Queue with JSON Lines file persistence.

    Each entry is kept in memory for fast iteration and simultaneously
    appended to a ``.jsonl`` file so that failures survive process restarts.
    Call ``load()`` at startup to restore entries from an existing file.

    Attributes:
        _file_path: Resolved path to the backing JSON Lines file.
        _entries: In-memory list of DLQ entries.
    """

    def __init__(self, file_path: str | Path) -> None:
        """Initialise the manager and ensure the parent directory exists.

        Args:
            file_path: Path to the JSON Lines file used for persistence.
                The parent directory is created automatically if missing.
        """
        self._file_path: Path = Path(file_path)
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        self._entries: list[DLQEntry] = []

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def add(self, record: RecordEnvelope, errors: list[str]) -> None:
        """Add a failed record to the DLQ and persist it to disk.

        Args:
            record: The record envelope that failed processing.
            errors: Error messages describing why the record failed.
        """
        entry = DLQEntry(record=record, errors=list(errors))
        self._entries.append(entry)
        self._persist_entry(entry)

    def clear(self) -> None:
        """Remove all entries from memory and truncate the backing file."""
        self._entries.clear()
        # Truncate the file to zero bytes
        self._file_path.write_text("", encoding="utf-8")

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_entries(self) -> list[DLQEntry]:
        """Return all in-memory DLQ entries.

        Returns:
            List of all DLQEntry objects currently held in memory.
        """
        return list(self._entries)

    def retry_eligible(self, max_retries: int) -> list[DLQEntry]:
        """Return entries that have not yet reached the retry limit.

        Args:
            max_retries: Maximum allowed retry attempts.

        Returns:
            List of entries where ``retry_count < max_retries``.
        """
        return [e for e in self._entries if e.retry_count < max_retries]

    @property
    def size(self) -> int:
        """Number of entries currently held in memory."""
        return len(self._entries)

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _persist_entry(self, entry: DLQEntry) -> None:
        """Append a single DLQ entry as a JSON line to the backing file.

        Datetime values are serialised using ``.isoformat()``.

        Args:
            entry: The DLQEntry to serialise and append.
        """
        record = entry.record
        row = {
            "record": {
                "data": record.data,
                "source": record.source,
                "record_id": record.record_id,
                "timestamp": (
                    record.timestamp.isoformat()
                    if isinstance(record.timestamp, datetime)
                    else str(record.timestamp)
                ),
                "metadata": record.metadata,
                "errors": record.errors,
            },
            "errors": entry.errors,
            "failed_at": (
                entry.failed_at.isoformat()
                if isinstance(entry.failed_at, datetime)
                else str(entry.failed_at)
            ),
            "retry_count": entry.retry_count,
        }
        with self._file_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    def load(self) -> None:
        """Load entries from the backing file into memory.

        Replaces any existing in-memory entries.  Lines that cannot be parsed
        are silently skipped so that a partially-written file does not block
        startup.
        """
        self._entries.clear()

        if not self._file_path.exists():
            return

        with self._file_path.open("r", encoding="utf-8") as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    rec_data = row["record"]
                    record = RecordEnvelope(
                        data=rec_data["data"],
                        source=rec_data["source"],
                        record_id=rec_data["record_id"],
                        timestamp=datetime.fromisoformat(rec_data["timestamp"]),
                        metadata=rec_data.get("metadata", {}),
                        errors=rec_data.get("errors", []),
                    )
                    entry = DLQEntry(
                        record=record,
                        errors=row.get("errors", []),
                        failed_at=datetime.fromisoformat(row["failed_at"]),
                        retry_count=row.get("retry_count", 0),
                    )
                    self._entries.append(entry)
                except (KeyError, ValueError, json.JSONDecodeError):
                    # Skip malformed lines — don't crash on corrupt files
                    continue
