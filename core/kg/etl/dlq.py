"""Dead Letter Queue (DLQ) manager for failed ETL records.

Provides:
- DLQEntry: dataclass holding a failed record with error context
- DLQManager: in-memory DLQ with add/get/retry/clear operations
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from kg.etl.models import RecordEnvelope


@dataclass
class DLQEntry:
    """A failed record stored in the Dead Letter Queue.

    Attributes:
        record: The original record envelope that failed processing.
        errors: Error messages describing why the record failed.
        failed_at: Timestamp when the failure occurred.
        retry_count: Number of times this record has been retried.
    """

    record: RecordEnvelope
    errors: list[str] = field(default_factory=list)
    failed_at: datetime = field(default_factory=datetime.now)
    retry_count: int = 0


class DLQManager:
    """In-memory Dead Letter Queue for failed ETL records.

    Stores failed records with error context and supports retrieval
    of retry-eligible entries based on a maximum retry count.
    """

    def __init__(self) -> None:
        self._entries: list[DLQEntry] = []

    def add(self, record: RecordEnvelope, errors: list[str]) -> None:
        """Add a failed record to the DLQ.

        Args:
            record: The record that failed processing.
            errors: Error messages describing the failure.
        """
        self._entries.append(DLQEntry(record=record, errors=list(errors)))

    def get_entries(self) -> list[DLQEntry]:
        """Return all entries in the DLQ.

        Returns:
            List of all DLQ entries.
        """
        return list(self._entries)

    def retry_eligible(self, max_retries: int) -> list[DLQEntry]:
        """Return entries that have not exceeded the retry limit.

        Args:
            max_retries: Maximum allowed retry attempts.

        Returns:
            List of entries where ``retry_count < max_retries``.
        """
        return [e for e in self._entries if e.retry_count < max_retries]

    def clear(self) -> None:
        """Remove all entries from the DLQ."""
        self._entries.clear()

    @property
    def size(self) -> int:
        """Number of entries currently in the DLQ."""
        return len(self._entries)
